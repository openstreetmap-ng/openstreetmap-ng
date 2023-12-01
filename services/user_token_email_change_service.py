import secrets
from uuid import UUID

from db import DB
from lib.crypto import hash_b
from limits import USER_TOKEN_EMAIL_CHANGE_EXPIRE
from models.db.user_token_email_change import UserTokenEmailChange
from utils import utcnow


# TODO: rename to user email change service and code related methods
class UserTokenEmailChangeService:
    @staticmethod
    async def create(user_id: int, from_email: str, to_email: str) -> tuple[UUID, str]:
        """
        Create a new user email change token.

        Returns a tuple of the token id and the token string.
        """

        # TODO: check different + format

        token_str = secrets.token_urlsafe(32)
        token_hashed = hash_b(token_str, context=None)

        async with DB() as session:
            token = UserTokenEmailChange(
                user_id=user_id,
                token_hashed=token_hashed,
                expires_at=utcnow() + USER_TOKEN_EMAIL_CHANGE_EXPIRE,
                from_email=from_email,
                to_email=to_email,
            )

            session.add(token)

        return token.id, token_str
