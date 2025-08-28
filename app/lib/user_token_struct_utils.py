import logging
from base64 import b32decode, b32encode

import cython
from google.protobuf.message import DecodeError
from pydantic import SecretStr

from app.lib.crypto import hash_compare, hmac_bytes
from app.lib.exceptions_context import raise_for
from app.models.proto.server_pb2 import StatelessUserTokenStruct, UserTokenStruct
from app.queries.user_query import UserQuery

if cython.compiled:
    from cython.cimports.libc.math import ceil
else:
    from math import ceil


class UserTokenStructUtils:
    @staticmethod
    def from_str(s: SecretStr) -> UserTokenStruct:
        """Parse the given string into a user token struct."""
        try:
            payload = b32decode(_add_b32_padding(s.get_secret_value()), casefold=True)
        except ValueError:
            logging.info('User token is not well-encoded')
            raise_for.bad_user_token_struct()

        try:
            return UserTokenStruct.FromString(payload)
        except DecodeError:
            logging.info('User token is malformed')
            raise_for.bad_user_token_struct()

    @staticmethod
    async def from_str_stateless(s: SecretStr) -> StatelessUserTokenStruct:
        """Parse the given string into a stateless user token struct."""
        try:
            payload = b32decode(_add_b32_padding(s.get_secret_value()), casefold=True)
        except ValueError:
            logging.info('User token is not well-encoded')
            raise_for.bad_user_token_struct()

        if len(payload) <= 32:
            logging.info('User token is too short')
            raise_for.bad_user_token_struct()

        serialized = payload[:-32]
        signature = payload[-32:]
        if not hash_compare(serialized, signature, hash_func=hmac_bytes):
            logging.info('User token signature mismatch')
            raise_for.bad_user_token_struct()

        try:
            token = StatelessUserTokenStruct.FromString(serialized)
        except DecodeError:
            # Warning instead of Info because this is a signed token
            logging.warning('User token is malformed')
            raise_for.bad_user_token_struct()

        user = await UserQuery.find_by_id(token.user_id)  # type: ignore
        if user is None or not hash_compare(user['email'], token.email_hashed):
            logging.info('User token email mismatch')
            raise_for.bad_user_token_struct()

        return token

    @staticmethod
    def to_str(u: UserTokenStruct | StatelessUserTokenStruct) -> str:
        """Convert the given user token struct into a string."""
        payload = u.SerializeToString()

        if isinstance(u, StatelessUserTokenStruct):
            payload += hmac_bytes(payload)

        return b32encode(payload).rstrip(b'=').lower().decode('ascii')


@cython.cfunc
def _add_b32_padding(s: str) -> str:
    s_len: cython.Py_ssize_t = len(s)
    pad_len: cython.int = int(ceil(s_len / 8) * 8 - s_len)
    return s + ('=' * pad_len)
