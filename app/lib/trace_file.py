import logging
from collections.abc import Sequence

import magic

from app.lib.exceptions_context import raise_for
from app.lib.trace_file_processor.base import TraceFileProcessor
from app.lib.trace_file_processor.bzip2 import Bzip2FileProcessor
from app.lib.trace_file_processor.gzip import GzipFileProcessor
from app.lib.trace_file_processor.tar import TarFileProcessor
from app.lib.trace_file_processor.xml import XmlFileProcessor
from app.lib.trace_file_processor.zip import ZipFileProcessor
from app.lib.trace_file_processor.zstd import ZstdFileProcessor

# maps content_type to processor type
_trace_file_processors: dict[str, TraceFileProcessor] = {
    processor.media_type: processor
    for processor in (
        Bzip2FileProcessor,
        GzipFileProcessor,
        TarFileProcessor,
        XmlFileProcessor,
        ZipFileProcessor,
        ZstdFileProcessor,
    )
}


class TraceFile:
    @staticmethod
    def extract(buffer: bytes) -> Sequence[bytes]:
        """
        Extract the trace files from the buffer.

        The buffer may be compressed, in which case it will be decompressed first.
        """

        # multiple layers allow to handle nested archives such as .tar.gz
        # the use of range here is a cython optimization
        for layer in range(1, 2 + 1):
            content_type = magic.from_buffer(buffer[:2048], mime=True)
            logging.debug('Trace file layer %d is %r', layer, content_type)

            # get the appropriate processor
            processor = _trace_file_processors.get(content_type)
            if processor is None:
                raise_for().trace_file_unsupported_format(content_type)

            result = processor.decompress(buffer)

            # bytes: further processing is needed
            if isinstance(result, bytes):
                buffer = result
                continue

            # list of bytes: finished
            return result

        # raise on too many layers
        raise_for().trace_file_archive_too_deep()

    @staticmethod
    def compress(buffer: bytes) -> tuple[bytes, str]:
        """
        Compress the trace file buffer.

        Returns the compressed buffer and the file name suffix.
        """
        return ZstdFileProcessor.compress(buffer), ZstdFileProcessor.suffix

    @staticmethod
    def decompress_if_needed(buffer: bytes, file_id: str) -> bytes:
        """
        Decompress the trace file buffer if needed.
        """
        if file_id.endswith(ZstdFileProcessor.suffix):
            return ZstdFileProcessor.decompress(buffer)

        return buffer
