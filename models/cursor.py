from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta
from typing import Self
from uuid import UUID

from betterproto import which_one_of

from lib.exceptions import raise_for
from proto.cursor import Cursor as ProtoCursor
from utils import utcnow


class Cursor:
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

        proto = ProtoCursor()

        if isinstance(self.id, int):
            proto.int_id = self.id
        elif isinstance(self.id, UUID):
            proto.uuid_id = self.id.bytes
        else:
            raise NotImplementedError(f'Unsupported id type {type(self.id)!r}')

        if self.time is not None:
            proto.time = self.time

        return urlsafe_b64encode(bytes(proto)).decode()

    @classmethod
    def from_str(cls, s: str, *, expire: timedelta | None = None) -> Self:
        """
        Parse the given string into a cursor.

        Optionally check whether the cursor is expired.
        """

        try:
            proto = ProtoCursor().parse(urlsafe_b64decode(s))
        except Exception:
            raise_for().bad_cursor()

        # optionally check expiration
        if expire is not None and (proto.time is None or proto.time + expire < utcnow()):
            raise_for().cursor_expired()

        _, val = which_one_of(proto, 'id')

        return cls(id=val, time=proto.time)
