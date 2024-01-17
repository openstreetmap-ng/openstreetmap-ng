import logging
from hmac import compare_digest

from sqlalchemy import func, select

from app.db import DB
from app.libc.crypto import hash_bytes
from app.models.db.user_token_account_confirm import UserTokenAccountConfirm
from app.models.msgspec.user_token_struct import UserTokenStruct


class UserTokenAccountConfirmRepository:
    @staticmethod
    async def find_one_by_token_struct(token_struct: UserTokenStruct) -> UserTokenAccountConfirm | None:
        """
        Find a user account confirmation token by token struct.
        """

        async with DB() as session:
            stmt = select(UserTokenAccountConfirm).where(
                UserTokenAccountConfirm.id == token_struct.id,
                UserTokenAccountConfirm.expires_at > func.now(),  # TODO: expires at check
            )

            token = await session.scalar(stmt)

        if not token:
            return None

        token_hashed = hash_bytes(token_struct.token, context=None)

        if not compare_digest(token.token_hashed, token_hashed):
            logging.debug('Invalid account confirmation token for id %r', token_struct.id)
            return None

        return token.user
