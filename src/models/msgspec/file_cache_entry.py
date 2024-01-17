from typing import Self

import msgspec

from src.utils import MSGSPEC_MSGPACK_DECODER, MSGSPEC_MSGPACK_ENCODER


class FileCacheEntry(msgspec.Struct, omit_defaults=True, forbid_unknown_fields=True, array_like=True):
    version: int = 1
    expires_at: int | None
    data: bytes

    def __init__(self, expires_at: int | None, data: bytes):
        self.expires_at = expires_at
        self.data = data

    def to_bytes(self) -> bytes:
        """
        Serialize the file cache meta struct into bytes.
        """

        return MSGSPEC_MSGPACK_ENCODER.encode(self)

    @classmethod
    def from_bytes(cls, buffer: bytes) -> Self:
        """
        Parse the given buffer into a file cache meta struct.
        """

        return MSGSPEC_MSGPACK_DECODER.decode(buffer, type=cls)
