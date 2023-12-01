import secrets
from uuid import UUID

from db import DB
from lib.crypto import hash_b
from limits import USER_TOKEN_SESSION_EXPIRE
from models.db.user_token_session import UserTokenSession
from utils import utcnow


class UserTokenSessionService:
    @staticmethod
    async def create(user_id: int) -> tuple[UUID, str]:
        """
        Create a new user session token.

        Returns a tuple of the session id and the token string.
        """

        token_str = secrets.token_urlsafe(32)
        token_hashed = hash_b(token_str, context=None)

        async with DB() as session:
            token = UserTokenSession(
                user_id=user_id,
                token_hashed=token_hashed,
                expires_at=utcnow() + USER_TOKEN_SESSION_EXPIRE,
            )

            session.add(token)

        return token.id, token_str
