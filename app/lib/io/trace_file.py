import logging
import tarfile
import zlib
from abc import ABC, abstractmethod
from asyncio import to_thread
from bz2 import BZ2Decompressor
from compression import zstd
from io import BytesIO
from tarfile import TarError
from typing import ClassVar, LiteralString, NamedTuple, override
from zipfile import BadZipFile, ZipFile

import cython
import magic
from sizestr import sizestr

from app.config import (
    TRACE_FILE_ARCHIVE_MAX_FILES,
    TRACE_FILE_COMPRESS_ZSTD_LEVEL,
    TRACE_FILE_COMPRESS_ZSTD_THREADS,
    TRACE_FILE_DECOMPRESSED_MAX_SIZE,
    TRACE_FILE_MAX_LAYERS,
    TRACE_FILE_RECOMPRESS_ZSTD_LEVEL,
)
from app.exceptions.context import raise_for
from app.models.types import StorageKey


class _CompressResult(NamedTuple):
    data: bytes
    suffix: LiteralString
    metadata: dict[str, str]


_ZSTD_SUFFIX = '.zst'
class TraceFile:
    @staticmethod
    def extract(buffer: bytes):
        """
        Extract the trace files from the buffer.
        The buffer may be compressed, in which case it will be decompressed first.
        """
        # multiple layers allow to handle nested archives such as .tar.gz
        # the use of range here is a cython optimization
        for layer in range(1, TRACE_FILE_MAX_LAYERS + 1):
            content_type = magic.from_buffer(buffer[:2048], mime=True)
            logging.debug('Trace file layer %d is %r', layer, content_type)

            # return if no processing needed
            if content_type in {'text/xml', 'application/xml', 'application/gpx+xml'}:
                _log_decompressed_size(content_type, len(buffer))
                return [buffer]

            # get the appropriate processor
            processor = _TRACE_PROCESSORS.get(content_type)
            if processor is None:
                raise_for.trace_file_unsupported_format(content_type)

            result = processor.decompress(buffer)

            # list of files: finished
            if not isinstance(result, bytes):
                return result

            # compressed blob: continue processing
            buffer = result

        # raise on too many layers
        raise_for.trace_file_archive_too_deep()

    @staticmethod
    async def compress(buffer: bytes):
        """Compress the trace file buffer. Returns the compressed buffer and the file name suffix."""
        return await _compress_zstd(buffer, level=TRACE_FILE_COMPRESS_ZSTD_LEVEL)

    @staticmethod
    async def recompress(buffer: bytes):
        """Compress the trace file buffer with the archival zstd level."""
        return await _compress_zstd(buffer, level=TRACE_FILE_RECOMPRESS_ZSTD_LEVEL)

    @staticmethod
    def decompress_if_needed(buffer: bytes, file_id: StorageKey):
        """Decompress the trace file buffer if needed."""
        return (
            _ZstdProcessor.decompress(buffer)
            if file_id.endswith(_ZSTD_SUFFIX)
            else buffer
        )


class _TraceProcessor(ABC):
    media_type: ClassVar[str]

    @classmethod
    @abstractmethod
    def decompress(cls, buffer: bytes) -> list[bytes] | bytes:
        """Decompress the buffer and return files data or a subsequent buffer."""
        ...


class _Bzip2Processor(_TraceProcessor):
    media_type = 'application/x-bzip2'

    @classmethod
    @override
    def decompress(cls, buffer: bytes):
        decompressor = BZ2Decompressor()
        try:
            result = decompressor.decompress(buffer, TRACE_FILE_DECOMPRESSED_MAX_SIZE)
        except OSError, ValueError:
            raise_for.trace_file_archive_corrupted(cls.media_type)
        if not decompressor.needs_input:
            raise_for.input_too_big(TRACE_FILE_DECOMPRESSED_MAX_SIZE)
        if not decompressor.eof or decompressor.unused_data:
            raise_for.trace_file_archive_corrupted(cls.media_type)

        _log_decompressed_size(cls.media_type, len(result))
        return result


class _GzipProcessor(_TraceProcessor):
    media_type = 'application/gzip'

    @classmethod
    @override
    def decompress(cls, buffer: bytes):
        decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16)
        try:
            result = decompressor.decompress(buffer, TRACE_FILE_DECOMPRESSED_MAX_SIZE)
        except zlib.error:
            raise_for.trace_file_archive_corrupted(cls.media_type)
        if decompressor.unconsumed_tail:
            raise_for.input_too_big(TRACE_FILE_DECOMPRESSED_MAX_SIZE)
        if not decompressor.eof or decompressor.unused_data:
            raise_for.trace_file_archive_corrupted(cls.media_type)

        _log_decompressed_size(cls.media_type, len(result))
        return result


class _TarProcessor(_TraceProcessor):
    media_type = 'application/x-tar'

    @classmethod
    @override
    def decompress(cls, buffer: bytes):
        try:
            # pure tar uses no compression, so it's efficient to read files from the memory buffer
            # 'r:' opens for reading exclusively without compression (safety check)
            with tarfile.open(fileobj=BytesIO(buffer), mode='r:') as archive:
                result: list[bytes] = []

                for info in archive:
                    if not info.isfile():
                        continue

                    if len(result) >= TRACE_FILE_ARCHIVE_MAX_FILES:
                        raise_for.trace_file_archive_too_many_files()

                    file = archive.extractfile(info)
                    assert file is not None
                    with file:
                        result.append(file.read())

                logging.debug(
                    'Trace %r archive contains %d files',
                    cls.media_type,
                    len(result),
                )

                # not checking for the total size of the files - there is no compression
                # the output size will not exceed the input size
                return result

        except TarError:
            raise_for.trace_file_archive_corrupted(cls.media_type)


class _ZipProcessor(_TraceProcessor):
    media_type = 'application/zip'

    @classmethod
    @override
    def decompress(cls, buffer: bytes):
        try:
            with ZipFile(BytesIO(buffer)) as archive:
                result: list[bytes] = []
                remaining_size: cython.size_t = TRACE_FILE_DECOMPRESSED_MAX_SIZE

                for info in archive.infolist():
                    if info.is_dir():
                        continue

                    if len(result) >= TRACE_FILE_ARCHIVE_MAX_FILES:
                        raise_for.trace_file_archive_too_many_files()

                    with archive.open(info) as f:
                        file_data = f.read(remaining_size)
                        remaining_size -= len(file_data)
                        result.append(file_data)
                        if remaining_size == 0 and f.read(1):
                            raise_for.input_too_big(TRACE_FILE_DECOMPRESSED_MAX_SIZE)

                logging.debug(
                    'Trace %r archive contains %d files',
                    cls.media_type,
                    len(result),
                )

        except BadZipFile:
            raise_for.trace_file_archive_corrupted(cls.media_type)

        total_size = TRACE_FILE_DECOMPRESSED_MAX_SIZE - remaining_size
        _log_decompressed_size(cls.media_type, total_size)
        return result


class _ZstdProcessor(_TraceProcessor):
    media_type = 'application/zstd'

    @classmethod
    @override
    def decompress(cls, buffer: bytes):
        decompressor = zstd.ZstdDecompressor()
        try:
            result = decompressor.decompress(buffer, TRACE_FILE_DECOMPRESSED_MAX_SIZE)
        except zstd.ZstdError:
            raise_for.trace_file_archive_corrupted(cls.media_type)
        if not decompressor.eof:
            if not decompressor.needs_input:
                raise_for.input_too_big(TRACE_FILE_DECOMPRESSED_MAX_SIZE)
            raise_for.trace_file_archive_corrupted(cls.media_type)
        if decompressor.unused_data:
            raise_for.trace_file_archive_corrupted(cls.media_type)

        _log_decompressed_size(cls.media_type, len(result))
        return result


@cython.cfunc
def _log_decompressed_size(media_type: str, size: cython.size_t):
    logging.debug('Trace %r decompressed size is %s', media_type, sizestr(size))


_TRACE_PROCESSORS: dict[str, type[_TraceProcessor]] = {
    processor.media_type: processor
    for processor in (
        _Bzip2Processor,
        _GzipProcessor,
        _TarProcessor,
        _ZipProcessor,
        _ZstdProcessor,
    )
}


async def _compress_zstd(buffer: bytes, *, level: int):
    result = await to_thread(
        zstd.compress,
        buffer,
        options={
            zstd.CompressionParameter.compression_level: level,
            zstd.CompressionParameter.nb_workers: TRACE_FILE_COMPRESS_ZSTD_THREADS,
        },
    )
    logging.debug(
        'Trace file zstd-compressed at level %d size is %s',
        level,
        sizestr(len(result)),
    )
    return _CompressResult(result, _ZSTD_SUFFIX, {'zstd_level': str(level)})
