import logging
from hmac import compare_digest

from sqlalchemy import func, select

from app.db import db
from app.lib.crypto import hash_bytes
from app.lib.options_context import apply_options_context
from app.models.db.user_token_session import UserTokenSession
from app.models.msgspec.user_token_struct import UserTokenStruct


class UserTokenSessionQuery:
    @staticmethod
    async def find_one_by_token_struct(token_struct: UserTokenStruct) -> UserTokenSession | None:
        """
        Find a user session token by token struct.
        """
        async with db() as session:
            stmt = select(UserTokenSession).where(
                UserTokenSession.id == token_struct.id,
                UserTokenSession.expires_at > func.statement_timestamp(),  # TODO: expires at check
            )
            stmt = apply_options_context(stmt)
            token = await session.scalar(stmt)

        if token is None:
            return None

        token_hashed = hash_bytes(token_struct.token)

        if not compare_digest(token.token_hashed, token_hashed):
            logging.debug('Invalid session token for id %r', token_struct.id)
            return None

        return token
