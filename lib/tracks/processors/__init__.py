from types import MappingProxyType

from lib.tracks.processors.base import FileProcessor
from lib.tracks.processors.bzip2 import Bzip2FileProcessor
from lib.tracks.processors.gzip import GzipFileProcessor
from lib.tracks.processors.tar import TarFileProcessor
from lib.tracks.processors.xml import XmlFileProcessor
from lib.tracks.processors.zip import ZipFileProcessor

# maps content_type to processor type
# the processor reads from stdin and writes to stdout
TRACE_FILE_PROCESSORS: dict[str, FileProcessor] = MappingProxyType(
    {
        XmlFileProcessor.media_type: XmlFileProcessor,
        TarFileProcessor.media_type: TarFileProcessor,
        ZipFileProcessor.media_type: ZipFileProcessor,
        GzipFileProcessor.media_type: GzipFileProcessor,
        Bzip2FileProcessor.media_type: Bzip2FileProcessor,
    }
)
