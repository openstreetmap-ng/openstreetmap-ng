import logging
import tarfile
from collections.abc import Sequence
from io import BytesIO
from typing import override

from app.lib.exceptions_context import raise_for
from app.lib.trace_file_processor.base import TraceFileProcessor
from app.limits import TRACE_FILE_ARCHIVE_MAX_FILES


class TarFileProcessor(TraceFileProcessor):
    media_type = 'application/x-tar'

    @override
    @classmethod
    def decompress(cls, buffer: bytes) -> Sequence[bytes]:
        # pure tar uses no compression, so it's efficient to read files from the memory buffer
        # r: opens for reading exclusively without compression (safety check)
        with tarfile.open(fileobj=BytesIO(buffer), mode='r:') as archive:
            infos = tuple(info for info in archive.getmembers() if info.isfile())
            infos_len = len(infos)
            logging.debug('Trace %r archive contains %d files', cls.media_type, infos_len)

            if infos_len > TRACE_FILE_ARCHIVE_MAX_FILES:
                raise_for().trace_file_archive_too_many_files()

            # not checking for the total size of the files - there is no compression
            # the output size will not exceed the input size
            return tuple(archive.extractfile(info).read() for info in infos)
