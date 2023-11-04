import logging
import subprocess
import tarfile
import zipfile
from abc import ABC
from io import BytesIO
from typing import Sequence

import anyio
from humanize import naturalsize

from lib.exceptions import Exceptions
from limits import (TRACE_FILE_ARCHIVE_MAX_FILES,
                    TRACE_FILE_COMPRESS_ZSTD_LEVEL,
                    TRACE_FILE_COMPRESS_ZSTD_THREADS,
                    TRACE_FILE_UNCOMPRESSED_MAX_SIZE)


class TracksProcessor(ABC):
    format: str

    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes] | bytes:
        raise NotImplementedError()


class XmlTracksProcessor(TracksProcessor, ABC):
    format = 'text/xml'

    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes]:
        logging.debug('Trace %r uncompressed size is %s', cls.format, naturalsize(len(buffer), True))
        return [buffer]


class TarTracksProcessor(TracksProcessor, ABC):
    format = 'application/x-tar'

    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes]:
        # tar uses no compression, so it's efficient to read files from the memory buffer
        with tarfile.open(fileobj=BytesIO(buffer), mode='r:') as tar:
            members = tar.getmembers()
            logging.debug('Trace %r archive contains %d files', cls.format, len(members))

            if len(members) > TRACE_FILE_ARCHIVE_MAX_FILES:
                Exceptions.get().raise_for_trace_file_archive_too_many_files()

            result = [None] * len(members)

            for i, member in enumerate(members):
                file = tar.extractfile(member)
                if not file:
                    # skip directories
                    continue
                result[i] = file.read()

            return result


class ZipTracksProcessor(TracksProcessor, ABC):
    format = 'application/zip'

    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes]:
        with zipfile.ZipFile(BytesIO(buffer)) as zip:
            filenames = zip.namelist()
            logging.debug('Trace %r archive contains %d files', cls.format, len(filenames))

        if len(filenames) > TRACE_FILE_ARCHIVE_MAX_FILES:
            Exceptions.get().raise_for_trace_file_archive_too_many_files()

        result = [None] * len(filenames)
        result_size = 0

        async def read_file(i: int, filename: bytes) -> None:
            nonlocal result_size

            async with await anyio.open_process(['unzip', '-p', '-', filename], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
                await process.stdin.send(buffer)
                file_result = await process.stdout.receive(max_bytes=TRACE_FILE_UNCOMPRESSED_MAX_SIZE + 1)

            if process.returncode != 0:
                Exceptions.get().raise_for_trace_file_archive_corrupted(cls.format)

            result[i] = file_result
            result_size += len(file_result)

            if result_size > TRACE_FILE_UNCOMPRESSED_MAX_SIZE:
                Exceptions.get().raise_for_input_too_big(result_size)

        async with anyio.create_task_group() as tg:
            for i, filename in enumerate(filenames):
                tg.start_soon(read_file, i, filename)

        logging.debug('Trace %r archive uncompressed size is %s', cls.format, naturalsize(len(result), True))
        return result


class CompressionTracksProcessor(TracksProcessor, ABC):
    format: str
    command: Sequence[str]

    @classmethod
    async def decompress(cls, buffer: bytes) -> bytes:
        async with await anyio.open_process(cls.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
            await process.stdin.send(buffer)
            result = await process.stdout.receive(max_bytes=TRACE_FILE_UNCOMPRESSED_MAX_SIZE + 1)

        if process.returncode != 0:
            Exceptions.get().raise_for_trace_file_archive_corrupted(cls.format)
        if len(result) > TRACE_FILE_UNCOMPRESSED_MAX_SIZE:
            Exceptions.get().raise_for_input_too_big(len(result))

        logging.debug('Trace %r archive uncompressed size is %s', cls.format, naturalsize(len(result), True))
        return result


class GzipTracksProcessor(CompressionTracksProcessor, ABC):
    format = 'application/gzip'
    command = ['gzip', '-d', '-c']


class Bzip2TracksProcessor(CompressionTracksProcessor, ABC):
    format = 'application/x-bzip2'
    command = ['bzip2', '-d', '-c']


class ZstdTracksProcessor(CompressionTracksProcessor, ABC):
    format = 'application/zstd'
    command = ['zstd', '-d', '-c']
    suffix = '.zst'

    @classmethod
    async def compress(cls, buffer: bytes) -> bytes:
        buffer_size = len(buffer)

        for level_max_size, level in TRACE_FILE_COMPRESS_ZSTD_LEVEL:
            if buffer_size <= level_max_size:
                break

        command = [
            'zstd', '-c',
            f'-{level}',
            f'-T{TRACE_FILE_COMPRESS_ZSTD_THREADS}',
            '--stream-size', len(buffer)
        ]

        async with await anyio.open_process(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
            await process.stdin.send(buffer)
            result = await process.stdout.receive(max_bytes=TRACE_FILE_UNCOMPRESSED_MAX_SIZE * 2)

        if process.returncode != 0:
            raise RuntimeError('zstd compression failed')

        logging.debug('Trace %r archive compressed size is %s', cls.format, naturalsize(len(result), True))
        return result


# maps content type to processor command
# the processor reads from stdin and writes to stdout
TRACKS_PROCESSORS: dict[str, TracksProcessor] = {
    XmlTracksProcessor.format: XmlTracksProcessor,
    TarTracksProcessor.format: TarTracksProcessor,
    ZipTracksProcessor.format: ZipTracksProcessor,
    GzipTracksProcessor.format: GzipTracksProcessor,
    Bzip2TracksProcessor.format: Bzip2TracksProcessor,
}
