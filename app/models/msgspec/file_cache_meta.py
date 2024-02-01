from typing import Self

import msgspec

from app.utils import MSGSPEC_MSGPACK_DECODER, MSGSPEC_MSGPACK_ENCODER


class FileCacheMeta(msgspec.Struct, omit_defaults=True):
    version: int
    expires_at: int | None
    data: bytes

    def to_bytes(self) -> bytes:
        """
        Serialize the file cache meta struct into bytes.
        """

        return MSGSPEC_MSGPACK_ENCODER.encode(self)

    @classmethod
    def v1(cls, expires_at: int | None, data: bytes) -> Self:
        """
        Create a file cache meta struct with version 1.
        """

        return cls(version=1, expires_at=expires_at, data=data)

    @classmethod
    def from_bytes(cls, buffer: bytes) -> Self:
        """
        Parse the given buffer into a file cache meta struct.
        """

        return MSGSPEC_MSGPACK_DECODER.decode(buffer, type=cls)
