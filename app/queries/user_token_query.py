import logging
from typing import Literal, overload

from psycopg.rows import dict_row

from app.db import db2
from app.lib.crypto import hash_compare
from app.models.db.user_token import (
    USER_TOKEN_EXPIRE,
    UserToken,
    UserTokenEmailChange,
    UserTokenEmailReply,
    UserTokenType,
)
from app.models.proto.server_pb2 import UserTokenStruct
from app.models.types import Email


class UserTokenQuery:
    @staticmethod
    @overload
    async def find_one_by_token_struct(
        token_type: Literal['account_confirm', 'reset_password'],
        token_struct: UserTokenStruct,
        *,
        check_email_hash: bool = True,
    ) -> UserToken | None: ...
    @staticmethod
    @overload
    async def find_one_by_token_struct(
        token_type: Literal['email_change'],
        token_struct: UserTokenStruct,
        *,
        check_email_hash: bool = True,
    ) -> UserTokenEmailChange | None: ...
    @staticmethod
    @overload
    async def find_one_by_token_struct(
        token_type: Literal['email_reply'],
        token_struct: UserTokenStruct,
        *,
        check_email_hash: bool = True,
    ) -> UserTokenEmailReply | None: ...
    @staticmethod
    async def find_one_by_token_struct(
        token_type: UserTokenType,
        token_struct: UserTokenStruct,
        *,
        check_email_hash: bool = True,
    ) -> UserToken | None:
        """Find a user token by token struct."""
        async with db2() as conn:
            async with await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM user_token
                WHERE id = %s AND created_at + %s > statement_timestamp()
                """,
                (token_struct.id, USER_TOKEN_EXPIRE[token_type]),
            ) as r:
                token: UserToken | None = await r.fetchone()  # type: ignore
                if token is None:
                    return None

            if not hash_compare(token_struct.token, token['token_hashed']):
                logging.debug('Invalid user token secret for id %r', token_struct.id)
                return None

            if check_email_hash:
                async with await conn.execute(
                    """
                    SELECT email FROM "user"
                    WHERE id = %s
                    """,
                    (token['user_id'],),
                ) as r:
                    row = await r.fetchone()
                    if row is None:
                        return None
                    email: Email = row[0]

                if not hash_compare(email, token['user_email_hashed']):
                    logging.debug('Invalid user token email for id %r', token_struct.id)
                    return None

            return token
