from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_randbytes
from app.lib.crypto import hash_bytes
from app.lib.date_utils import utcnow
from app.limits import USER_TOKEN_EMAIL_CHANGE_EXPIRE
from app.models.db.user_token_email_change import UserTokenEmailChange
from app.models.proto.server_pb2 import UserTokenStruct
from app.models.types import EmailType


class UserTokenEmailChangeService:
    @staticmethod
    async def create(new_email: EmailType) -> UserTokenStruct:
        """
        Create a new user email change token.
        """
        user = auth_user(required=True)
        user_email_hashed = hash_bytes(user.email.encode())
        token_bytes = buffered_randbytes(32)
        token_hashed = hash_bytes(token_bytes)
        async with db_commit() as session:
            token = UserTokenEmailChange(
                user_id=user.id,
                user_email_hashed=user_email_hashed,
                token_hashed=token_hashed,
                expires_at=utcnow() + USER_TOKEN_EMAIL_CHANGE_EXPIRE,
                new_email=new_email,
            )
            session.add(token)

        return UserTokenStruct(id=token.id, token=token_bytes)
