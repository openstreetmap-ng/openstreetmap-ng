import logging
from hmac import compare_digest

from sqlalchemy import func, select

from app.db import DB
from app.lib.crypto import hash_bytes
from app.models.db.user_token_session import UserTokenSession
from app.models.msgspec.user_token_struct import UserTokenStruct


class UserTokenSessionRepository:
    @staticmethod
    async def find_one_by_token_struct(token_struct: UserTokenStruct) -> UserTokenSession | None:
        """
        Find a user session token by token struct.
        """

        async with DB() as session:
            stmt = select(UserTokenSession).where(
                UserTokenSession.id == token_struct.id,
                UserTokenSession.expires_at > func.now(),  # TODO: expires at check
            )

            token = await session.scalar(stmt)

        if not token:
            return None

        token_hashed = hash_bytes(token_struct.token, context=None)

        if not compare_digest(token.token_hashed, token_hashed):
            logging.debug('Invalid session token for id %r', token_struct.id)
            return None

        return token.user
