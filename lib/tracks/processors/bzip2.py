from abc import ABC

from lib.tracks.processors.base import CompressionFileProcessor


class Bzip2FileProcessor(CompressionFileProcessor, ABC):
    media_type = 'application/x-bzip2'
    command = ('bzip2', '-d', '-c')
