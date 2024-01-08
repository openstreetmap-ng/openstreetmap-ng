import logging
import subprocess
from abc import ABC
from collections.abc import Sequence

import anyio
from humanize import naturalsize

from src.lib.exceptions import raise_for
from src.limits import TRACE_FILE_UNCOMPRESSED_MAX_SIZE


class FileProcessor(ABC):
    media_type: str

    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes] | bytes:
        """
        Decompress the buffer and return files data or a subsequent buffer.
        """

        raise NotImplementedError


class CompressionFileProcessor(FileProcessor, ABC):
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
            raise_for().trace_file_archive_corrupted(cls.media_type)
        if len(result) > TRACE_FILE_UNCOMPRESSED_MAX_SIZE:
            raise_for().input_too_big(len(result))

        logging.debug('Trace %r archive uncompressed size is %s', cls.media_type, naturalsize(len(result), True))
        return result
