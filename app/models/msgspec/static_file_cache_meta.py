from typing import Self

import msgspec

from app.utils import MSGPACK_ENCODE, msgpack_decoder


class StaticFileCacheMeta(msgspec.Struct):
    # no versioning: non-persistent cache
    content: bytes
    headers: dict[str, str]
    media_type: str

    def to_bytes(self) -> bytes:
        """
        Serialize the static file cache meta struct into bytes.
        """

        return MSGPACK_ENCODE(self)

    @classmethod
    def from_bytes(cls, buffer: bytes) -> Self:
        """
        Parse the given buffer into a file cache meta struct.
        """

        return _decode(buffer)


_decode = msgpack_decoder(StaticFileCacheMeta).decode
