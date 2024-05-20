from app.config import SMTP_MESSAGES_FROM_HOST
from app.db import db_commit
from app.lib.auth_context import auth_context, auth_user
from app.lib.buffered_random import buffered_randbytes
from app.lib.crypto import hash_bytes
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.limits import USER_TOKEN_EMAIL_REPLY_EXPIRE
from app.models.db.user_token_email_reply import UserTokenEmailReply
from app.models.mail_source import MailSource
from app.models.msgspec.user_token_struct import UserTokenStruct
from app.queries.user_token_email_reply_query import UserTokenEmailReplyQuery
from app.services.message_service import MessageService


async def _create_token(replying_user_id: int, mail_source: MailSource) -> UserTokenStruct:
    """
    Create a new user email reply token.

    Replying user can use this token to send a message to the current user.
    """
    token_bytes = buffered_randbytes(32)
    token_hashed = hash_bytes(token_bytes)

    async with db_commit() as session:
        token = UserTokenEmailReply(
            user_id=replying_user_id,
            token_hashed=token_hashed,
            expires_at=utcnow() + USER_TOKEN_EMAIL_REPLY_EXPIRE,
            mail_source=mail_source,
            to_user_id=auth_user().id,
        )
        session.add(token)

    return UserTokenStruct.v1(id=token.id, token=token_bytes)


class UserTokenEmailReplyService:
    @staticmethod
    async def create_address(replying_user_id: int, mail_source: MailSource) -> str:
        """
        Create a new user email reply address.

        Replying user can use this address to send a message to the current user.
        """
        token = await _create_token(replying_user_id, mail_source)
        reply_address = f'{token}@{SMTP_MESSAGES_FROM_HOST}'
        return reply_address

    @staticmethod
    async def reply(reply_address: str, subject: str, body: str) -> None:
        """
        Reply to a user with a message.
        """
        token = await UserTokenEmailReplyQuery.find_one_by_reply_address(reply_address)
        if token is None:
            raise_for().bad_user_token_struct()

        # TODO: if the key is leaked, there is no way to revoke it (possible targeted spam)
        with auth_context(token.user, scopes=()):
            await MessageService.send(token.to_user_id, subject, body)
