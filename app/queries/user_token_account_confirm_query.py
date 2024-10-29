import logging
from hmac import compare_digest

from sqlalchemy import func, select

from app.db import db
from app.lib.crypto import hash_bytes
from app.lib.options_context import apply_options_context
from app.models.db.user_token_account_confirm import UserTokenAccountConfirm
from app.models.proto.server_pb2 import UserTokenStruct


class UserTokenAccountConfirmQuery:
    @staticmethod
    async def find_one_by_token_struct(token_struct: UserTokenStruct) -> UserTokenAccountConfirm | None:
        """
        Find a user account confirmation token by token struct.
        """
        async with db() as session:
            stmt = select(UserTokenAccountConfirm).where(
                UserTokenAccountConfirm.id == token_struct.id,
                UserTokenAccountConfirm.expires_at > func.statement_timestamp(),  # TODO: expires at check
            )
            stmt = apply_options_context(stmt)
            token = await session.scalar(stmt)

        if token is None:
            return None

        token_hashed = hash_bytes(token_struct.token)

        if not compare_digest(token.token_hashed, token_hashed):
            logging.debug('Invalid account confirmation token for id %r', token_struct.id)
            return None

        return token
