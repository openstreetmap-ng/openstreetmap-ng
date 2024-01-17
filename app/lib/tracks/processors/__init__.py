from app.lib.tracks.processors.base import FileProcessor
from app.lib.tracks.processors.bzip2 import Bzip2FileProcessor
from app.lib.tracks.processors.gzip import GzipFileProcessor
from app.lib.tracks.processors.tar import TarFileProcessor
from app.lib.tracks.processors.xml import XmlFileProcessor
from app.lib.tracks.processors.zip import ZipFileProcessor

# maps content_type to processor type
# the processor reads from stdin and writes to stdout
TRACE_FILE_PROCESSORS: dict[str, FileProcessor] = {
    XmlFileProcessor.media_type: XmlFileProcessor,
    TarFileProcessor.media_type: TarFileProcessor,
    ZipFileProcessor.media_type: ZipFileProcessor,
    GzipFileProcessor.media_type: GzipFileProcessor,
    Bzip2FileProcessor.media_type: Bzip2FileProcessor,
}
