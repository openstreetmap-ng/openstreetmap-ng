import logging
from abc import ABC
from collections.abc import Sequence

from app.lib.tracks.processors.base import FileProcessor
from app.libc.naturalsize import naturalsize


class XmlFileProcessor(FileProcessor, ABC):
    media_type = 'text/xml'

    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes]:
        logging.debug('Trace %r uncompressed size is %s', cls.media_type, naturalsize(len(buffer)))
        return [buffer]
