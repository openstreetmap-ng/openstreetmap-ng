from abc import ABC
from collections.abc import Sequence


class TraceFileProcessor(ABC):
    media_type: str

    @classmethod
    def decompress(cls, buffer: bytes) -> Sequence[bytes] | bytes:
        """
        Decompress the buffer and return files data or a subsequent buffer.
        """

        raise NotImplementedError
