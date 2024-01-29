from typing import Self

import msgspec

from app.utils import MSGSPEC_MSGPACK_DECODER, MSGSPEC_MSGPACK_ENCODER


class FileCacheEntry(msgspec.Struct, omit_defaults=True):
    expires_at: int | None
    data: bytes

    version: int = 1

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
