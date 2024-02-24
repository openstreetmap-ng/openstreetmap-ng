import gzip
import logging
from typing import override

from app.lib.exceptions_context import raise_for
from app.lib.naturalsize import naturalsize
from app.lib.trace_file_processor.base import TraceFileProcessor
from app.limits import TRACE_FILE_UNCOMPRESSED_MAX_SIZE


class GzipFileProcessor(TraceFileProcessor):
    media_type = 'application/gzip'

    @override
    @classmethod
    def decompress(cls, buffer: bytes) -> bytes:
        try:
            result = gzip.decompress(buffer)
        except (EOFError, gzip.BadGzipFile()):
            raise_for().trace_file_archive_corrupted(cls.media_type)

        if len(result) > TRACE_FILE_UNCOMPRESSED_MAX_SIZE:
            raise_for().input_too_big(TRACE_FILE_UNCOMPRESSED_MAX_SIZE)

        logging.debug('Trace %r archive uncompressed size is %s', cls.media_type, naturalsize(len(result)))
        return result
