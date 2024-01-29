from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Self
from uuid import UUID

import msgspec

from app.lib.exceptions_context import raise_for
from app.utils import MSGSPEC_MSGPACK_DECODER, MSGSPEC_MSGPACK_ENCODER


class UserTokenStruct(msgspec.Struct, omit_defaults=True, forbid_unknown_fields=True, array_like=True):
    id: int | UUID
    token: bytes

    version: int = 1

    def __str__(self) -> str:
        """
        Return a string representation of the user token struct.
        """

        return urlsafe_b64encode(MSGSPEC_MSGPACK_ENCODER.encode(self)).decode()

    @classmethod
    def from_str(cls, s: str) -> Self:
        """
        Parse the given string into a user token struct.
        """

        buff = urlsafe_b64decode(s)

        try:
            obj: Self = MSGSPEC_MSGPACK_DECODER.decode(buff, type=cls)
        except Exception:
            raise_for().bad_user_token_struct()

        return obj
