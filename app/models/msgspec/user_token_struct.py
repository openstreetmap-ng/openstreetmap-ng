from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Self
from uuid import UUID

import msgspec

from app.lib.exceptions_context import raise_for
from app.utils import MSGPACK_ENCODE, msgpack_decoder


class UserTokenStruct(msgspec.Struct, forbid_unknown_fields=True, array_like=True):
    version: int
    id: int | UUID
    token: bytes

    def __str__(self) -> str:
        """
        Return a string representation of the user token struct.
        """

        return urlsafe_b64encode(MSGPACK_ENCODE(self)).decode()

    @classmethod
    def v1(cls, id: int | UUID, token: bytes) -> Self:
        """
        Create a user token struct with version 1.
        """

        return cls(version=1, id=id, token=token)

    @classmethod
    def from_str(cls, s: str) -> Self:
        """
        Parse the given string into a user token struct.
        """

        buff = urlsafe_b64decode(s)

        try:
            obj: Self = _decode(buff)
        except Exception:
            raise_for().bad_user_token_struct()

        return obj


_decode = msgpack_decoder(UserTokenStruct).decode
