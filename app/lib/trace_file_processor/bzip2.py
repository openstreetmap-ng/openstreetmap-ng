from app.lib.trace_file_processor.base import CompressionFileProcessor
from app.utils import raise_if_program_unavailable

raise_if_program_unavailable('bzip2')


class Bzip2FileProcessor(CompressionFileProcessor):
    media_type = 'application/x-bzip2'
    command = ('bzip2', '-d', '-c')
