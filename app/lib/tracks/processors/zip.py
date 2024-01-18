import logging
import subprocess
import zipfile
from abc import ABC
from collections.abc import Sequence
from io import BytesIO

import anyio

from app.lib.tracks.processors.base import FileProcessor
from app.libc.exceptions_context import raise_for
from app.libc.naturalsize import naturalsize
from app.limits import TRACE_FILE_ARCHIVE_MAX_FILES, TRACE_FILE_UNCOMPRESSED_MAX_SIZE


class ZipFileProcessor(FileProcessor, ABC):
    media_type = 'application/zip'

    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes]:
        with zipfile.ZipFile(BytesIO(buffer)) as archive:
            filenames = archive.namelist()
            logging.debug('Trace %r archive contains %d files', cls.media_type, len(filenames))

        if len(filenames) > TRACE_FILE_ARCHIVE_MAX_FILES:
            raise_for().trace_file_archive_too_many_files()

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
                raise_for().trace_file_archive_corrupted(cls.media_type)

            result[i] = file_result
            result_size += len(file_result)

            if result_size > TRACE_FILE_UNCOMPRESSED_MAX_SIZE:
                raise_for().input_too_big(result_size)

        async with anyio.create_task_group() as tg:
            for i, filename in enumerate(filenames):
                tg.start_soon(read_file, i, filename)

        logging.debug('Trace %r archive uncompressed size is %s', cls.media_type, naturalsize(len(result)))
        return result
