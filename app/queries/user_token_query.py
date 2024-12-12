import logging
from hmac import compare_digest
from typing import TypeVar

from sqlalchemy import func, select

from app.db import db
from app.lib.crypto import hash_bytes
from app.lib.options_context import apply_options_context
from app.models.db.user import User
from app.models.db.user_token import UserToken
from app.models.proto.server_pb2 import UserTokenStruct

_T = TypeVar('_T', bound=UserToken)


# TODO: expires_at cleanup
class UserTokenQuery:
    @staticmethod
    async def find_one_by_token_struct(
        model: type[_T], token_struct: UserTokenStruct, *, check_email_hash: bool = True
    ) -> _T | None:
        """
        Find a user token by token struct.
        """
        async with db() as session:
            stmt = select(model).where(
                model.id == token_struct.id,
                model.created_at + model.__expire__ > func.statement_timestamp(),
            )
            stmt = apply_options_context(stmt)
            token = await session.scalar(stmt)
            if token is None:
                return None

            token_hashed = hash_bytes(token_struct.token)
            if not compare_digest(token.token_hashed, token_hashed):
                logging.debug('Invalid user token secret for id %r', token_struct.id)
                return None

            if check_email_hash:
                stmt = select(User.email).where(User.id == token.user_id)
                user_email = await session.scalar(stmt)
                if user_email is None:
                    return None
                user_email_hashed = hash_bytes(user_email.encode())
                if not compare_digest(token.user_email_hashed, user_email_hashed):
                    logging.debug('Invalid user token email for id %r', token_struct.id)
                    return None

            return token
