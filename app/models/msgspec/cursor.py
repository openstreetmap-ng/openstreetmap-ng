from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta

import msgspec

from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.utils import MSGPACK_ENCODE, typed_msgpack_decoder


class Cursor(msgspec.Struct, forbid_unknown_fields=True, array_like=True):
    version: int
    id: int  # fallback to 0 on None
    time: datetime | None

    def __str__(self) -> str:
        """
        Return a string representation of the cursor.
        """
        return urlsafe_b64encode(MSGPACK_ENCODE(self)).decode()

    @classmethod
    def v1(cls, id: int, *, time: datetime | None = None) -> 'Cursor':
        """
        Create a cursor with version 1.
        """
        return cls(version=1, id=id, time=time)

    @classmethod
    def from_str(cls, s: str, *, expire: timedelta | None = None) -> 'Cursor':
        """
        Parse the given string into a cursor.

        Optionally check whether the cursor is expired.
        """
        buff = urlsafe_b64decode(s)

        try:
            obj: Cursor = _decode(buff)
        except Exception:
            raise_for().bad_cursor()

        # optionally check expiration
        if (expire is not None) and (obj.time is None or obj.time + expire < utcnow()):
            raise_for().cursor_expired()

        return obj


_decode = typed_msgpack_decoder(Cursor).decode
