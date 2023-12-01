import logging
from base64 import urlsafe_b64encode
from hmac import compare_digest
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from db import DB
from lib.crypto import hash_b
from models.db.user_token_email_reply import UserTokenEmailReply


class UserTokenEmailReplyRepository:
    @staticmethod
    async def find_one_by_reply_address(reply_address: str) -> UserTokenEmailReply | None:
        """
        Find a user email reply token by reply email address.
        """

        try:
            combined, _ = reply_address.split('@', maxsplit=1)
            combined_b = urlsafe_b64encode(combined.encode())
            if len(combined_b) != (16 + 32):
                raise ValueError
        except Exception:
            logging.debug('Invalid reply_address format %r', reply_address)
            return None

        token_id = UUID(bytes=combined_b[:16])

        async with DB() as session:
            stmt = (
                select(UserTokenEmailReply)
                .options(joinedload(UserTokenEmailReply.user, UserTokenEmailReply.to_user))
                .where(
                    UserTokenEmailReply.id == token_id,
                    UserTokenEmailReply.expires_at > func.now(),
                )
            )

            token = await session.scalar(stmt)

        if not token:
            return None

        token_b = combined_b[16:]
        token_hashed = hash_b(token_b, context=None)

        if not compare_digest(token.token_hashed, token_hashed):
            logging.debug('Invalid key for reply_address %r', reply_address)
            return None

        return token
