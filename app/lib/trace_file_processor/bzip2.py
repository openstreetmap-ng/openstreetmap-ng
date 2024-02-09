import bz2
import logging
from io import BytesIO
from typing import override

from app.lib.exceptions_context import raise_for
from app.lib.naturalsize import naturalsize
from app.lib.trace_file_processor.base import TraceFileProcessor
from app.limits import TRACE_FILE_UNCOMPRESSED_MAX_SIZE


class Bzip2FileProcessor(TraceFileProcessor):
    media_type = 'application/x-bzip2'

    @override
    @classmethod
    async def decompress(cls, buffer: bytes) -> bytes:
        with bz2.open(BytesIO(buffer), 'rb') as f:
            result = f.read(TRACE_FILE_UNCOMPRESSED_MAX_SIZE + 1)

        result_len = len(result)
        if result_len > TRACE_FILE_UNCOMPRESSED_MAX_SIZE:
            raise_for().input_too_big(TRACE_FILE_UNCOMPRESSED_MAX_SIZE)

        logging.debug('Trace %r archive uncompressed size is %s', cls.media_type, naturalsize(result_len))
        return result
