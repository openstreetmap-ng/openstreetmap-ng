import logging
from collections.abc import Sequence
from typing import override

from app.lib.naturalsize import naturalsize
from app.lib.trace_file_processor.base import TraceFileProcessor


class XmlFileProcessor(TraceFileProcessor):
    media_type = 'text/xml'

    @override
    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes]:
        logging.debug('Trace %r uncompressed size is %s', cls.media_type, naturalsize(len(buffer)))
        return (buffer,)
