import logging
import tarfile
from abc import ABC
from collections.abc import Sequence
from io import BytesIO

from lib.exceptions import raise_for
from lib.tracks.processors.base import FileProcessor
from limits import TRACE_FILE_ARCHIVE_MAX_FILES


class TarFileProcessor(FileProcessor, ABC):
    media_type = 'application/x-tar'

    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes]:
        # pure tar uses no compression, so it's efficient to read files from the memory buffer
        # r: opens for reading exclusively without compression (safety check)
        with tarfile.open(fileobj=BytesIO(buffer), mode='r:') as archive:
            members = archive.getmembers()
            logging.debug('Trace %r archive contains %d files', cls.media_type, len(members))

            if len(members) > TRACE_FILE_ARCHIVE_MAX_FILES:
                raise_for().trace_file_archive_too_many_files()

            result = [None] * len(members)

            for i, member in enumerate(members):
                file = archive.extractfile(member)
                if not file:
                    # skip directories
                    continue
                result[i] = file.read()

            return result
