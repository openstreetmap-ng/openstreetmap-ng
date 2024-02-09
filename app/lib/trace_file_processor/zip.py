import logging
import zipfile
from collections.abc import Sequence
from io import BytesIO
from typing import override

import cython

from app.lib.exceptions_context import raise_for
from app.lib.naturalsize import naturalsize
from app.lib.trace_file_processor.base import TraceFileProcessor
from app.limits import TRACE_FILE_ARCHIVE_MAX_FILES, TRACE_FILE_UNCOMPRESSED_MAX_SIZE


class ZipFileProcessor(TraceFileProcessor):
    media_type = 'application/zip'

    @override
    @classmethod
    async def decompress(cls, buffer: bytes) -> Sequence[bytes]:
        with zipfile.ZipFile(BytesIO(buffer)) as archive:
            infos = tuple(info for info in archive.infolist() if not info.is_dir())
            infos_len = len(infos)
            logging.debug('Trace %r archive contains %d files', cls.media_type, infos_len)

            if infos_len > TRACE_FILE_ARCHIVE_MAX_FILES:
                raise_for().trace_file_archive_too_many_files()

            result = []
            result_size: cython.int = 0

            for info in infos:
                file = archive.read(info)
                result.append(file)
                result_size += len(file)

                if result_size > TRACE_FILE_UNCOMPRESSED_MAX_SIZE:
                    raise_for().input_too_big(TRACE_FILE_UNCOMPRESSED_MAX_SIZE)

        logging.debug('Trace %r archive uncompressed size is %s', cls.media_type, naturalsize(result_size))
        return result
