import secrets
from datetime import timedelta

from models.db.user_token import UserToken
from utils import utcnow

_EXPIRE = timedelta(days=365)


class UserTokenSession(UserToken):
    __tablename__ = 'user_token_session'

    # TODO: SQL
    @classmethod
    async def create_for_user(cls, user_id: SequentialId) -> tuple[ObjectId, str]:
        key = secrets.token_urlsafe(32)
        token = cls(
            user_id=user_id,
            expires_at=utcnow() + _EXPIRE,
            key_hashed=hash_hex(key, context=None),
        )
        await token.create()
        return token.id, key
