import logging
import tarfile
import zlib
from abc import ABC, abstractmethod
from asyncio import to_thread
from bz2 import BZ2Decompressor
from io import BytesIO
from tarfile import TarError
from typing import ClassVar, LiteralString, NamedTuple, override
from zipfile import BadZipFile, ZipFile

import cython
import magic
from sizestr import sizestr
from zstandard import (
    DECOMPRESSION_RECOMMENDED_OUTPUT_SIZE,
    ZstdCompressor,
    ZstdDecompressor,
    ZstdError,
)

from app.config import (
    TRACE_FILE_ARCHIVE_MAX_FILES,
    TRACE_FILE_COMPRESS_ZSTD_LEVEL,
    TRACE_FILE_COMPRESS_ZSTD_THREADS,
    TRACE_FILE_DECOMPRESSED_MAX_SIZE,
    TRACE_FILE_MAX_LAYERS,
)
from app.lib.exceptions_context import raise_for
from app.models.types import StorageKey


class _CompressResult(NamedTuple):
    data: bytes
    suffix: LiteralString
    metadata: dict[str, str]


_ZSTD_SUFFIX = '.zst'
_ZSTD_METADATA: dict[str, str] = {'zstd_level': str(TRACE_FILE_COMPRESS_ZSTD_LEVEL)}


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
        result = await to_thread(
            ZstdCompressor(
                level=TRACE_FILE_COMPRESS_ZSTD_LEVEL,
                threads=TRACE_FILE_COMPRESS_ZSTD_THREADS,
            ).compress,
            buffer,
        )
        logging.debug('Trace file zstd-compressed size is %s', sizestr(len(result)))
        return _CompressResult(result, _ZSTD_SUFFIX, _ZSTD_METADATA)

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
        except (OSError, ValueError):
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
                infos = [info for info in archive.getmembers() if info.isfile()]
                logging.debug(
                    'Trace %r archive contains %d files',
                    cls.media_type,
                    len(infos),
                )

                if len(infos) > TRACE_FILE_ARCHIVE_MAX_FILES:
                    raise_for.trace_file_archive_too_many_files()

                # not checking for the total size of the files - there is no compression
                # the output size will not exceed the input size
                return [archive.extractfile(info).read() for info in infos]  # pyright: ignore[reportOptionalMemberAccess]

        except TarError:
            raise_for.trace_file_archive_corrupted(cls.media_type)


class _ZipProcessor(_TraceProcessor):
    media_type = 'application/zip'

    @classmethod
    @override
    def decompress(cls, buffer: bytes):
        try:
            with ZipFile(BytesIO(buffer)) as archive:
                infos = [info for info in archive.infolist() if not info.is_dir()]
                logging.debug(
                    'Trace %r archive contains %d files',
                    cls.media_type,
                    len(infos),
                )

                if len(infos) > TRACE_FILE_ARCHIVE_MAX_FILES:
                    raise_for.trace_file_archive_too_many_files()

                result: list[bytes] = []
                remaining_size: cython.size_t = TRACE_FILE_DECOMPRESSED_MAX_SIZE

                for info in infos:
                    with archive.open(info) as f:
                        file_data = f.read(remaining_size)
                        remaining_size -= len(file_data)
                        result.append(file_data)
                        if remaining_size == 0 and f.read(1):
                            raise_for.input_too_big(TRACE_FILE_DECOMPRESSED_MAX_SIZE)

        except BadZipFile:
            raise_for.trace_file_archive_corrupted(cls.media_type)

        total_size = TRACE_FILE_DECOMPRESSED_MAX_SIZE - remaining_size
        _log_decompressed_size(cls.media_type, total_size)
        return result


class _ZstdProcessor(_TraceProcessor):
    media_type = 'application/zstd'

    @classmethod
    @override
    def decompress(
        cls,
        buffer: bytes,
        *,
        chunk_size: cython.size_t = DECOMPRESSION_RECOMMENDED_OUTPUT_SIZE,
    ):
        decompressor = ZstdDecompressor().decompressobj()
        chunks: list[bytes] = []
        total_size: cython.size_t = 0

        try:
            i: cython.size_t
            for i in range(0, len(buffer), chunk_size):
                chunk = decompressor.decompress(buffer[i : i + chunk_size])
                chunks.append(chunk)
                total_size += len(chunk)
                if total_size > TRACE_FILE_DECOMPRESSED_MAX_SIZE:
                    raise_for.input_too_big(TRACE_FILE_DECOMPRESSED_MAX_SIZE)
        except ZstdError:
            raise_for.trace_file_archive_corrupted(cls.media_type)
        if not decompressor.eof or decompressor.unused_data:
            raise_for.trace_file_archive_corrupted(cls.media_type)

        _log_decompressed_size(cls.media_type, total_size)
        return b''.join(chunks)


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
