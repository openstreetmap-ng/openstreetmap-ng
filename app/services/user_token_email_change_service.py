from hmac import compare_digest

from sqlalchemy import delete, select, update

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_randbytes
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.models.db.user import User
from app.models.db.user_token_email_change import UserTokenEmailChange
from app.models.proto.server_pb2 import UserTokenStruct
from app.models.types import EmailType
from app.queries.user_token_email_change_query import UserTokenEmailChangeQuery


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
                new_email=new_email,
            )
            session.add(token)

        return UserTokenStruct(id=token.id, token=token_bytes)

    @staticmethod
    async def confirm(token_struct: UserTokenStruct) -> None:
        """
        Confirm a user email change.
        """
        token = await UserTokenEmailChangeQuery.find_one_by_token_struct(token_struct)
        if token is None:
            raise_for.bad_user_token_struct()

        async with db_commit() as session:
            # prevent race conditions
            await session.connection(execution_options={'isolation_level': 'REPEATABLE READ'})

            if (
                await session.execute(delete(UserTokenEmailChange).where(UserTokenEmailChange.id == token_struct.id))
            ).rowcount != 1:
                raise_for.bad_user_token_struct()
            await session.commit()

            # avoiding with_for_update() because hash_bytes is slow
            stmt = select(User.email).where(User.id == token.user_id)
            user_email = await session.scalar(stmt)
            if user_email is None:
                raise_for.bad_user_token_struct()

            user_email_hashed = hash_bytes(user_email.encode())
            if not compare_digest(token.user_email_hashed, user_email_hashed):
                raise_for.bad_user_token_struct()

            await session.execute(
                update(User)
                .where(User.id == token.user_id, User.email == user_email)
                .values({User.email: token.new_email})
                .inline()
            )
