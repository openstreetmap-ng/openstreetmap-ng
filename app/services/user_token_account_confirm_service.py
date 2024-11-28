from sqlalchemy import delete, update

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_randbytes
from app.lib.crypto import hash_bytes
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.limits import USER_TOKEN_ACCOUNT_CONFIRM_EXPIRE
from app.models.db.user import User, UserStatus
from app.models.db.user_token_account_confirm import UserTokenAccountConfirm
from app.models.proto.server_pb2 import UserTokenStruct
from app.queries.user_token_account_confirm_query import UserTokenAccountConfirmQuery


class UserTokenAccountConfirmService:
    @staticmethod
    async def create() -> UserTokenStruct:
        """
        Create a new user account confirmation token.
        """
        user = auth_user(required=True)
        user_email_hashed = hash_bytes(user.email.encode())
        token_bytes = buffered_randbytes(32)
        token_hashed = hash_bytes(token_bytes)
        async with db_commit() as session:
            token = UserTokenAccountConfirm(
                user_id=user.id,
                user_email_hashed=user_email_hashed,
                token_hashed=token_hashed,
                expires_at=utcnow() + USER_TOKEN_ACCOUNT_CONFIRM_EXPIRE,
            )
            session.add(token)

        return UserTokenStruct(id=token.id, token=token_bytes)

    @staticmethod
    async def confirm(token_struct: UserTokenStruct) -> None:
        """
        Confirm a user account.
        """
        token = await UserTokenAccountConfirmQuery.find_one_by_token_struct(token_struct)
        if token is None:
            raise_for.bad_user_token_struct()

        async with db_commit() as session:
            # prevent race conditions
            await session.connection(execution_options={'isolation_level': 'REPEATABLE READ'})

            delete_stmt = delete(UserTokenAccountConfirm).where(UserTokenAccountConfirm.id == token_struct.id)
            if (await session.execute(delete_stmt)).rowcount != 1:
                raise_for.bad_user_token_struct()

            update_stmt = (
                update(User)
                .where(
                    User.id == token.user_id,
                    User.status == UserStatus.pending_activation,
                )
                .values({User.status: UserStatus.active})
                .inline()
            )
            await session.execute(update_stmt)
