from base64 import b32decode, b32encode

import cython
from google.protobuf.message import DecodeError
from pydantic import SecretStr

from app.lib.exceptions_context import raise_for
from app.models.proto.server_pb2 import UserTokenStruct

if cython.compiled:
    from cython.cimports.libc.math import ceil
else:
    from math import ceil


class UserTokenStructUtils:
    @staticmethod
    def from_str(s: SecretStr) -> UserTokenStruct:
        """
        Parse the given string into a user token struct.
        """
        try:
            return UserTokenStruct.FromString(b32decode(_add_b32_padding(s.get_secret_value()), casefold=True))
        except DecodeError:
            raise_for.bad_user_token_struct()

    @staticmethod
    def to_str(u: UserTokenStruct) -> str:
        """
        Convert the given user token struct into a string.
        """
        return b32encode(u.SerializeToString()).rstrip(b'=').lower().decode('ascii')


@cython.cfunc
def _add_b32_padding(s: str) -> str:
    s_len: cython.int = len(s)
    pad_len: cython.int = int(ceil(s_len / 8) * 8 - s_len)
    return s + ('=' * pad_len)
