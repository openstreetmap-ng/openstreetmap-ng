import logging
from typing import override

from zstandard import ZstdCompressor, ZstdDecompressor, ZstdError

from app.lib.exceptions_context import raise_for
from app.lib.naturalsize import naturalsize
from app.lib.trace_file_processor.base import TraceFileProcessor
from app.limits import (
    TRACE_FILE_COMPRESS_ZSTD_LEVEL,
    TRACE_FILE_COMPRESS_ZSTD_THREADS,
    TRACE_FILE_UNCOMPRESSED_MAX_SIZE,
)


class ZstdFileProcessor(TraceFileProcessor):
    media_type = 'application/zstd'
    suffix = '.zst'

    @override
    @classmethod
    def decompress(cls, buffer: bytes) -> bytes:
        try:
            result = ZstdDecompressor().decompress(buffer, allow_extra_data=False)
        except ZstdError:
            raise_for().trace_file_archive_corrupted(cls.media_type)

        if len(result) > TRACE_FILE_UNCOMPRESSED_MAX_SIZE:
            raise_for().input_too_big(TRACE_FILE_UNCOMPRESSED_MAX_SIZE)

        logging.debug('Trace %r archive uncompressed size is %s', cls.media_type, naturalsize(len(result)))
        return result

    @classmethod
    def compress(cls, buffer: bytes) -> bytes:
        result = ZstdCompressor(
            level=TRACE_FILE_COMPRESS_ZSTD_LEVEL,
            threads=TRACE_FILE_COMPRESS_ZSTD_THREADS,
        ).compress(buffer)

        logging.debug('Trace %r archive compressed size is %s', cls.media_type, naturalsize(len(result)))
        return result
