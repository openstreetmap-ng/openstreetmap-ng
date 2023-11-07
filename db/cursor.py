import struct
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta
from typing import Self

from lib.exceptions import Exceptions
from utils import utcnow


class Cursor:
    def __init__(self, id: int | None, time: datetime | None):
        if id is None:
            id = 0
        self.id = id
        self.time = time

    def to_str(self) -> str:
        if isinstance(self.id, int):
            id_data = struct.pack('>Q', self.last_seen_id)
        else:
            raise NotImplementedError(f'Unsupported id type {type(self.id)!r}')

        if isinstance(self.time, datetime):
            timestamp = self.time.timestamp()
            time_data = struct.pack('>d', timestamp)
        elif self.time is None:
            time_data = b''

        packed = id_data + time_data

        if len(packed) not in (8, 12, 16, 20):
            raise RuntimeError(f'Unexpected cursor packed length {len(packed)}')

        return urlsafe_b64encode(packed).decode()

    @classmethod
    def from_str(cls, cursor_str: str, expire: timedelta | None = None) -> Self:
        packed = urlsafe_b64decode(cursor_str)

        try:
            if len(packed) == 8:
                id_data = packed
                id, = struct.unpack('>Q', id_data)
                time = None
            elif len(packed) == 16:
                id_data, time_data = packed[:8], packed[8:]
                id, = struct.unpack('>Q', id_data)
                timestamp, = struct.unpack('>d', time_data)
                time = datetime.utcfromtimestamp(timestamp)
            else:
                raise Exception()

        except Exception:
            Exceptions.get().raise_for_bad_cursor()

        if expire and time + expire < utcnow():
            Exceptions.get().raise_for_cursor_expired()

        return cls(id, time)
