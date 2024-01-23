from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta
from typing import Self
from uuid import UUID

import msgspec

from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.utils import MSGSPEC_MSGPACK_DECODER, MSGSPEC_MSGPACK_ENCODER


class Cursor(msgspec.Struct, omit_defaults=True, forbid_unknown_fields=True, array_like=True):
    version: int = 1
    id: int | UUID
    time: datetime | None

    def __init__(self, id: int | UUID | None, time: datetime | None):
        if id is None:
            id = 0

        self.id = id
        self.time = time

    def __str__(self) -> str:
        """
        Return a string representation of the cursor.
        """

        return urlsafe_b64encode(MSGSPEC_MSGPACK_ENCODER.encode(self)).decode()

    @classmethod
    def from_str(cls, s: str, *, expire: timedelta | None = None) -> Self:
        """
        Parse the given string into a cursor.

        Optionally check whether the cursor is expired.
        """

        buff = urlsafe_b64decode(s)

        try:
            obj: Self = MSGSPEC_MSGPACK_DECODER.decode(buff, type=cls)
        except Exception:
            raise_for().bad_cursor()

        # optionally check expiration
        if expire is not None and (obj.time is None or obj.time + expire < utcnow()):
            raise_for().cursor_expired()

        return obj
