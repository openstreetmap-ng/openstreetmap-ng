# Constants
MODE_GENERIC: int
MODE_TEXT: int
MODE_FONT: int
version: str

# Exception
class error(Exception): ...

# Classes
class Compressor:
    def __init__(
        self,
        mode: int = MODE_GENERIC,
        quality: int = 11,
        lgwin: int = 22,
        lgblock: int = 0,
    ): ...
    def process(self, string: bytes) -> bytes: ...
    def flush(self) -> bytes: ...
    def finish(self) -> bytes: ...

class Decompressor:
    def __init__(self): ...
    def process(self, string: bytes) -> bytes: ...
    def is_finished(self) -> bool: ...

# Functions
def compress(
    string: bytes,
    mode: int = 0,
    quality: int = 11,
    lgwin: int = 22,
    lgblock: int = 0,
) -> bytes: ...
def decompress(string: bytes) -> bytes: ...
