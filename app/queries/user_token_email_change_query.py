import logging
from hmac import compare_digest

from sqlalchemy import func, select

from app.db import db
from app.lib.crypto import hash_bytes
from app.lib.options_context import apply_options_context
from app.limits import USER_TOKEN_EMAIL_CHANGE_EXPIRE
from app.models.db.user_token_email_change import UserTokenEmailChange
from app.models.proto.server_pb2 import UserTokenStruct


class UserTokenEmailChangeQuery:
    @staticmethod
    async def find_one_by_token_struct(token_struct: UserTokenStruct) -> UserTokenEmailChange | None:
        """
        Find an email change token by token struct.
        """
        async with db() as session:
            stmt = select(UserTokenEmailChange).where(
                UserTokenEmailChange.id == token_struct.id,
                UserTokenEmailChange.created_at + USER_TOKEN_EMAIL_CHANGE_EXPIRE > func.statement_timestamp(),
            )
            stmt = apply_options_context(stmt)
            token = await session.scalar(stmt)

        if token is None:
            return None

        token_hashed = hash_bytes(token_struct.token)
        if not compare_digest(token.token_hashed, token_hashed):
            logging.debug('Invalid email change token for id %r', token_struct.id)
            return None

        return token
