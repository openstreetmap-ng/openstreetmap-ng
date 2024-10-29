from app.db import db_commit
from app.lib.buffered_random import buffered_randbytes
from app.lib.crypto import hash_bytes
from app.lib.date_utils import utcnow
from app.limits import USER_TOKEN_RESET_PASSWORD_EXPIRE
from app.models.db.user import User
from app.models.db.user_token_reset_password import UserTokenResetPassword
from app.models.proto.server_pb2 import UserTokenStruct


class UserTokenResetPasswordService:
    @staticmethod
    async def create(user: User) -> UserTokenStruct:
        """
        Create a new user reset password token.
        """
        user_email_hashed = hash_bytes(user.email.encode())
        token_bytes = buffered_randbytes(32)
        token_hashed = hash_bytes(token_bytes)
        async with db_commit() as session:
            token = UserTokenResetPassword(
                user_id=user.id,
                user_email_hashed=user_email_hashed,
                token_hashed=token_hashed,
                expires_at=utcnow() + USER_TOKEN_RESET_PASSWORD_EXPIRE,
            )
            session.add(token)

        return UserTokenStruct(id=token.id, token=token_bytes)
