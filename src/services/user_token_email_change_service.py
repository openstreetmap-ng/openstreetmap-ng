import secrets

from src.db import DB
from src.lib.auth import auth_user
from src.lib.crypto import hash_b
from src.limits import USER_TOKEN_EMAIL_CHANGE_EXPIRE
from src.models.db.user_token_email_change import UserTokenEmailChange
from src.models.msgspec.user_token_struct import UserTokenStruct
from src.utils import utcnow


class UserTokenEmailChangeService:
    @staticmethod
    async def create(to_email: str) -> UserTokenStruct:
        """
        Create a new user email change token.
        """

        user = auth_user()
        token_b = secrets.token_bytes(32)
        token_hashed = hash_b(token_b, context=None)

        async with DB() as session:
            token = UserTokenEmailChange(
                user_id=user.id,
                token_hashed=token_hashed,
                expires_at=utcnow() + USER_TOKEN_EMAIL_CHANGE_EXPIRE,
                from_email=user.email,
                to_email=to_email,
            )

            session.add(token)

        return UserTokenStruct(token.id, token_b)
