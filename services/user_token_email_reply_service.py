import secrets
from base64 import urlsafe_b64encode

from config import SMTP_MESSAGES_FROM_HOST
from db import DB
from lib.crypto import hash_b
from limits import USER_TOKEN_EMAIL_REPLY_EXPIRE
from models.db.user_token_email_reply import UserTokenEmailReply
from models.mail_from_type import MailFromType
from utils import utcnow


class UserTokenEmailReplyService:
    @staticmethod
    async def create(from_user_id: int, source_type: MailFromType, to_user_id: int) -> str:
        """
        Create a new user email reply token.

        Returns a reply email address.
        """

        # TODO: if the key is leaked, there is no way to revoke it (possible targeted spam)

        token_b = secrets.token_bytes(32)
        token_hashed = hash_b(token_b, context=None)

        async with DB() as session:
            token = UserTokenEmailReply(
                user_id=from_user_id,
                token_hashed=token_hashed,
                expires_at=utcnow() + USER_TOKEN_EMAIL_REPLY_EXPIRE,
                source_type=source_type,
                to_user_id=to_user_id,
            )

            session.add(token)

        combined = urlsafe_b64encode(token.id.bytes + token_b).decode()
        reply_address = f'{combined}@{SMTP_MESSAGES_FROM_HOST}'
        return reply_address
