import logging
from email.utils import parseaddr
from hmac import compare_digest

from sqlalchemy import func, select

from app.db import db
from app.lib.crypto import hash_bytes
from app.lib.options_context import apply_options_context
from app.models.db.user_token_email_reply import UserTokenEmailReply
from app.models.msgspec.user_token_struct import UserTokenStruct


class UserTokenEmailReplyQuery:
    @staticmethod
    async def find_one_by_reply_address(reply_address: str) -> UserTokenEmailReply | None:
        """
        Find a user email reply token by reply email address.
        """
        # strip the name part: "abc" <foo@bar.com> -> foo@bar.com
        reply_address = parseaddr(reply_address)[1]

        try:
            token_str = reply_address.partition('@')[0]
            token_struct = UserTokenStruct.from_str(token_str)
        except Exception:
            logging.debug('Invalid reply_address format %r', reply_address)
            return None

        async with db() as session:
            stmt = select(UserTokenEmailReply).where(
                UserTokenEmailReply.id == token_struct.id,
                UserTokenEmailReply.expires_at > func.statement_timestamp(),
            )
            stmt = apply_options_context(stmt)
            token = await session.scalar(stmt)

        if token is None:
            return None

        token_hashed = hash_bytes(token_struct.token, context=None)

        if not compare_digest(token.token_hashed, token_hashed):
            logging.debug('Invalid reply token for reply_address %r', reply_address)
            return None

        return token
