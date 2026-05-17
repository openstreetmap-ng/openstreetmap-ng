import logging
from typing import Literal, overload

from app.db import db, db_fetchone, db_fetchval
from app.lib.auth.crypto import hash_compare
from app.models.db.user_token import (
    USER_TOKEN_EXPIRE,
    UserToken,
    UserTokenEmail,
    UserTokenEmailReply,
    UserTokenType,
)
from app.models.proto.server_pb2 import UserTokenStruct
from app.models.types import Email


class UserTokenQuery:
    @staticmethod
    @overload
    async def find_by_token_struct(
        token_type: Literal['reset_password'],
        token_struct: UserTokenStruct,
        *,
        check_email_hash: bool = True,
    ) -> UserToken | None: ...
    @staticmethod
    @overload
    async def find_by_token_struct(
        token_type: Literal['account_confirm', 'email_change'],
        token_struct: UserTokenStruct,
        *,
        check_email_hash: bool = True,
    ) -> UserTokenEmail | None: ...
    @staticmethod
    @overload
    async def find_by_token_struct(
        token_type: Literal['email_reply'],
        token_struct: UserTokenStruct,
        *,
        check_email_hash: bool = True,
    ) -> UserTokenEmailReply | None: ...
    @staticmethod
    async def find_by_token_struct(
        token_type: UserTokenType,
        token_struct: UserTokenStruct,
        *,
        check_email_hash: bool = True,
    ):
        """Find a user token by token struct."""
        token_id = token_struct.id
        expire = USER_TOKEN_EXPIRE[token_type]
        async with db() as conn:
            token = await db_fetchone(
                UserToken,
                t"""
                    SELECT * FROM user_token
                    WHERE id = {token_id} AND created_at + {expire} > statement_timestamp()
                """,
                conn=conn,
            )
            if token is None:
                return None

            if not hash_compare(token_struct.token, token['token_hashed']):
                logging.debug('Invalid user token secret for id %r', token_struct.id)
                return None

            if check_email_hash:
                user_id = token['user_id']
                email = await db_fetchval(
                    Email,
                    t'SELECT email FROM "user" WHERE id = {user_id}',
                    conn=conn,
                )
                if email is None:
                    return None

                if not hash_compare(email, token['user_email_hashed']):
                    logging.debug('Invalid user token email for id %r', token_struct.id)
                    return None

            return token
