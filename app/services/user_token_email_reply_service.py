import logging

from sqlalchemy.orm import joinedload
from sqlalchemy.sql import update

from app.config import SMTP_MESSAGES_FROM_HOST
from app.db import db_commit
from app.lib.auth_context import auth_context, auth_user
from app.lib.buffered_random import buffered_randbytes
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.lib.options_context import options_context
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.limits import EMAIL_REPLY_USAGE_LIMIT
from app.models.db.mail import MailSource
from app.models.db.user import User
from app.models.db.user_token_email_reply import UserTokenEmailReply
from app.models.proto.server_pb2 import UserTokenStruct
from app.models.types import EmailType
from app.queries.user_token_email_reply_query import UserTokenEmailReplyQuery
from app.services.message_service import MessageService


class UserTokenEmailReplyService:
    @staticmethod
    async def create_address(replying_user: User, mail_source: MailSource) -> EmailType:
        """
        Create a new user email reply address.

        Replying user can use this address to send a message to the current user.
        """
        token = await _create_token(replying_user, mail_source)
        token_str = UserTokenStructUtils.to_str(token)
        return EmailType(f'{token_str}@{SMTP_MESSAGES_FROM_HOST}')

    @staticmethod
    async def reply(reply_address: EmailType, subject: str, body: str) -> None:
        """
        Reply to a user with a message.
        """
        with options_context(joinedload(UserTokenEmailReply.user)):
            token = await UserTokenEmailReplyQuery.find_one_by_reply_address(reply_address)
            if token is None:
                raise_for.bad_user_token_struct()

        async with db_commit() as session:
            stmt = (
                update(UserTokenEmailReply)
                .where(
                    UserTokenEmailReply.id == token.id,
                    UserTokenEmailReply.usage_count < EMAIL_REPLY_USAGE_LIMIT,
                )
                .values({'usage_count': UserTokenEmailReply.usage_count + 1})
            )
            rows = await session.execute(stmt)
            if not rows.rowcount:
                logging.warning('UserTokenEmailReply usage limit exceeded for %d', token.id)
                raise_for.bad_user_token_struct()

        with auth_context(token.user, scopes=()):
            await MessageService.send(token.to_user_id, subject, body)


async def _create_token(replying_user: User, mail_source: MailSource) -> UserTokenStruct:
    """
    Create a new user email reply token.

    Replying user can use this token to send a message to the current user.
    """
    user_id = replying_user.id
    user_email_hashed = hash_bytes(replying_user.email.encode())
    token_bytes = buffered_randbytes(16)  # 128 bits
    token_hashed = hash_bytes(token_bytes)
    async with db_commit() as session:
        token = UserTokenEmailReply(
            user_id=user_id,
            user_email_hashed=user_email_hashed,
            token_hashed=token_hashed,
            mail_source=mail_source,
            to_user_id=auth_user(required=True).id,
        )
        session.add(token)
    return UserTokenStruct(id=token.id, token=token_bytes)
