import logging
from email.utils import parseaddr
from hmac import compare_digest

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.db import db
from app.lib.crypto import hash_bytes
from app.lib.options_context import apply_options_context
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.user import User
from app.models.db.user_token_email_reply import UserTokenEmailReply


class UserTokenEmailReplyQuery:
    @staticmethod
    async def find_one_by_reply_address(reply_address: str) -> UserTokenEmailReply | None:
        """
        Find a user email reply token by reply email address.
        """
        # strip the name part: "abc" <foo@bar.com> -> foo@bar.com
        reply_address = parseaddr(reply_address)[1]

        try:
            token_str = reply_address.split('@', maxsplit=1)[0]
            token_struct = UserTokenStructUtils.from_str(token_str)
        except Exception:
            logging.debug('Invalid reply_address format %r', reply_address)
            return None

        async with db() as session:
            stmt = (
                select(UserTokenEmailReply)
                .options(joinedload(UserTokenEmailReply.user).load_only(User.email))
                .where(
                    UserTokenEmailReply.id == token_struct.id,
                    UserTokenEmailReply.expires_at > func.statement_timestamp(),
                )
            )
            stmt = apply_options_context(stmt)
            token = await session.scalar(stmt)

        if token is None:
            return None

        token_hashed = hash_bytes(token_struct.token)
        if not compare_digest(token.token_hashed, token_hashed):
            logging.debug('Invalid reply token for reply_address %r', reply_address)
            return None

        user_email_hashed = hash_bytes(token.user.email.encode())
        if not compare_digest(token.user_email_hashed, user_email_hashed):
            logging.debug('Expired reply token for user %d', token.user_id)
            return None

        return token
