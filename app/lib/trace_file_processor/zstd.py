import logging
import subprocess

import anyio
import cython

from app.lib.naturalsize import naturalsize
from app.lib.trace_file_processor.base import CompressionFileProcessor
from app.limits import (
    TRACE_FILE_COMPRESS_ZSTD_LEVEL,
    TRACE_FILE_COMPRESS_ZSTD_THREADS,
    TRACE_FILE_UNCOMPRESSED_MAX_SIZE,
)
from app.utils import raise_if_program_unavailable

raise_if_program_unavailable('zstd')


@cython.cfunc
def _get_compression_level(buffer_size: int) -> int:
    for max_size, level in TRACE_FILE_COMPRESS_ZSTD_LEVEL:
        if buffer_size <= max_size:
            return level


class ZstdFileProcessor(CompressionFileProcessor):
    media_type = 'application/zstd'
    command = ('zstd', '-d', '-c')
    suffix = '.zst'

    @classmethod
    async def compress(cls, buffer: bytes) -> bytes:
        buffer_len = len(buffer)
        level = _get_compression_level(buffer_len)
        command = ('zstd', '-c', f'-{level}', f'-T{TRACE_FILE_COMPRESS_ZSTD_THREADS}', '--stream-size', buffer_len)

        async with await anyio.open_process(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        ) as process:
            await process.stdin.send(buffer)
            result = await process.stdout.receive(max_bytes=TRACE_FILE_UNCOMPRESSED_MAX_SIZE * 2)

        if process.returncode != 0:
            raise RuntimeError('zstd compression failed')

        logging.debug('Trace %r archive compressed size is %s', cls.media_type, naturalsize(len(result)))
        return result
