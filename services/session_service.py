import secrets

from db import DB
from lib.crypto import hash_b
from limits import USER_TOKEN_SESSION_EXPIRE
from models.db.user_token_session import UserTokenSession
from models.msgspec.user_token_struct import UserTokenStruct
from utils import utcnow


class SessionService:
    @staticmethod
    async def create_token(user_id: int) -> UserTokenStruct:
        """
        Create a new user session token.
        """

        token_b = secrets.token_bytes(32)
        token_hashed = hash_b(token_b, context=None)

        async with DB() as session:
            token = UserTokenSession(
                user_id=user_id,
                token_hashed=token_hashed,
                expires_at=utcnow() + USER_TOKEN_SESSION_EXPIRE,
            )

            session.add(token)

        return UserTokenStruct(token.id, token_b)
