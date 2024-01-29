import secrets

from app.config import SMTP_MESSAGES_FROM_HOST
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.crypto import hash_bytes
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.limits import USER_TOKEN_EMAIL_REPLY_EXPIRE
from app.models.db.user_token_email_reply import UserTokenEmailReply
from app.models.mail_from_type import MailFromType
from app.models.msgspec.user_token_struct import UserTokenStruct
from app.repositories.user_token_email_reply_repository import UserTokenEmailReplyRepository
from app.services.message_service import MessageService


class UserTokenEmailReplyService:
    @staticmethod
    async def _create(replying_user_id: int, source_type: MailFromType) -> UserTokenStruct:
        """
        Create a new user email reply token.

        Replying user can use this token to send a message to the current user.
        """

        token_bytes = secrets.token_bytes(32)
        token_hashed = hash_bytes(token_bytes, context=None)

        async with db() as session:
            token = UserTokenEmailReply(
                user_id=replying_user_id,
                token_hashed=token_hashed,
                expires_at=utcnow() + USER_TOKEN_EMAIL_REPLY_EXPIRE,
                source_type=source_type,
                to_user_id=auth_user().id,
            )

            session.add(token)

        return UserTokenStruct(id=token.id, token=token_bytes)

    @staticmethod
    async def create_address(replying_user_id: int, source_type: MailFromType) -> str:
        """
        Create a new user email reply address.

        Replying user can use this address to send a message to the current user.
        """

        token = await UserTokenEmailReplyService._create(replying_user_id, source_type)
        reply_address = f'{token}@{SMTP_MESSAGES_FROM_HOST}'
        return reply_address

    @staticmethod
    async def reply(reply_address: str, subject: str, body: str) -> None:
        """
        Reply to a user with a message.
        """

        token = await UserTokenEmailReplyRepository.find_one_by_reply_address(reply_address)

        if not token:
            raise_for().bad_user_token_struct()

        # TODO: if the key is leaked, there is no way to revoke it (possible targeted spam)
        with manual_auth_context(token.user_id):
            await MessageService.send(token.to_user_id, subject, body)
