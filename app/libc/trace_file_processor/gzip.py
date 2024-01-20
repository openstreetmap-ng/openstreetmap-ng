from app.libc.trace_file_processor.base import CompressionFileProcessor
from app.utils import raise_if_program_unavailable

raise_if_program_unavailable('gzip')


class GzipFileProcessor(CompressionFileProcessor):
    media_type = 'application/gzip'
    command = ('gzip', '-d', '-c')
