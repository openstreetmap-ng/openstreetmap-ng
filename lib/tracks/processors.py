import logging
import subprocess
import tarfile
import zipfile
from abc import ABC
from collections.abc import Sequence
from io import BytesIO
from types import MappingProxyType

import anyio
from humanize import naturalsize

from lib.exceptions import exceptions
from limits import (
    TRACE_FILE_ARCHIVE_MAX_FILES,
    TRACE_FILE_COMPRESS_ZSTD_LEVEL,
    TRACE_FILE_COMPRESS_ZSTD_THREADS,
    TRACE_FILE_UNCOMPRESSED_MAX_SIZE,
)


class TracksProcessor(ABC):
    media_type: str

    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes] | bytes:
        """
        Decompress the buffer and return files data or a subsequent buffer.
        """

        raise NotImplementedError


class XmlTracksProcessor(TracksProcessor, ABC):
    media_type = 'text/xml'

    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes]:
        logging.debug('Trace %r uncompressed size is %s', cls.media_type, naturalsize(len(buffer), True))
        return [buffer]


class TarTracksProcessor(TracksProcessor, ABC):
    media_type = 'application/x-tar'

    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes]:
        # pure tar uses no compression, so it's efficient to read files from the memory buffer
        # r: opens for reading exclusively without compression (safety check)
        with tarfile.open(fileobj=BytesIO(buffer), mode='r:') as archive:
            members = archive.getmembers()
            logging.debug('Trace %r archive contains %d files', cls.media_type, len(members))

            if len(members) > TRACE_FILE_ARCHIVE_MAX_FILES:
                exceptions().raise_for_trace_file_archive_too_many_files()

            result = [None] * len(members)

            for i, member in enumerate(members):
                file = archive.extractfile(member)
                if not file:
                    # skip directories
                    continue
                result[i] = file.read()

            return result


class ZipTracksProcessor(TracksProcessor, ABC):
    media_type = 'application/zip'

    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes]:
        with zipfile.ZipFile(BytesIO(buffer)) as archive:
            filenames = archive.namelist()
            logging.debug('Trace %r archive contains %d files', cls.media_type, len(filenames))

        if len(filenames) > TRACE_FILE_ARCHIVE_MAX_FILES:
            exceptions().raise_for_trace_file_archive_too_many_files()

        result = [None] * len(filenames)
        result_size = 0

        async def read_file(i: int, filename: bytes) -> None:
            nonlocal result_size

            async with await anyio.open_process(
                ['unzip', '-p', '-', filename],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            ) as process:
                await process.stdin.send(buffer)
                file_result = await process.stdout.receive(max_bytes=TRACE_FILE_UNCOMPRESSED_MAX_SIZE + 1)

            if process.returncode != 0:
                exceptions().raise_for_trace_file_archive_corrupted(cls.media_type)

            result[i] = file_result
            result_size += len(file_result)

            if result_size > TRACE_FILE_UNCOMPRESSED_MAX_SIZE:
                exceptions().raise_for_input_too_big(result_size)

        async with anyio.create_task_group() as tg:
            for i, filename in enumerate(filenames):
                tg.start_soon(read_file, i, filename)

        logging.debug('Trace %r archive uncompressed size is %s', cls.media_type, naturalsize(len(result), True))
        return result


class CompressionTracksProcessor(TracksProcessor, ABC):
    media_type: str
    command: Sequence[str]

    @classmethod
    async def decompress(cls, buffer: bytes) -> bytes:
        async with await anyio.open_process(
            cls.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        ) as process:
            await process.stdin.send(buffer)
            result = await process.stdout.receive(max_bytes=TRACE_FILE_UNCOMPRESSED_MAX_SIZE + 1)

        if process.returncode != 0:
            exceptions().raise_for_trace_file_archive_corrupted(cls.media_type)
        if len(result) > TRACE_FILE_UNCOMPRESSED_MAX_SIZE:
            exceptions().raise_for_input_too_big(len(result))

        logging.debug('Trace %r archive uncompressed size is %s', cls.media_type, naturalsize(len(result), True))
        return result


class GzipTracksProcessor(CompressionTracksProcessor, ABC):
    media_type = 'application/gzip'
    command = ('gzip', '-d', '-c')


class Bzip2TracksProcessor(CompressionTracksProcessor, ABC):
    media_type = 'application/x-bzip2'
    command = ('bzip2', '-d', '-c')


class ZstdTracksProcessor(CompressionTracksProcessor, ABC):
    media_type = 'application/zstd'
    command = ('zstd', '-d', '-c')
    suffix = '.zst'

    @classmethod
    async def compress(cls, buffer: bytes) -> bytes:
        buffer_size = len(buffer)
        level = next(filter(lambda max_size, _: buffer_size <= max_size, TRACE_FILE_COMPRESS_ZSTD_LEVEL))[1]
        command = ['zstd', '-c', f'-{level}', f'-T{TRACE_FILE_COMPRESS_ZSTD_THREADS}', '--stream-size', len(buffer)]

        async with await anyio.open_process(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        ) as process:
            await process.stdin.send(buffer)
            result = await process.stdout.receive(max_bytes=TRACE_FILE_UNCOMPRESSED_MAX_SIZE * 2)

        if process.returncode != 0:
            raise RuntimeError('zstd compression failed')

        logging.debug('Trace %r archive compressed size is %s', cls.media_type, naturalsize(len(result), True))
        return result


# maps content type to processor command
# the processor reads from stdin and writes to stdout
TRACKS_PROCESSORS = MappingProxyType(
    {
        XmlTracksProcessor.media_type: XmlTracksProcessor,
        TarTracksProcessor.media_type: TarTracksProcessor,
        ZipTracksProcessor.media_type: ZipTracksProcessor,
        GzipTracksProcessor.media_type: GzipTracksProcessor,
        Bzip2TracksProcessor.media_type: Bzip2TracksProcessor,
    }
)
