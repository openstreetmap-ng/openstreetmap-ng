import logging

from zid import zid

from app.config import EMAIL_REPLY_USAGE_LIMIT, SMTP_MESSAGES_FROM_HOST
from app.db import db
from app.lib.auth_context import auth_context, auth_user
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.mail import MailSource
from app.models.db.user import User
from app.models.db.user_token import UserTokenEmailReplyInit
from app.models.proto.server_pb2 import UserTokenStruct
from app.models.types import Email, UserId, UserTokenId
from app.queries.user_query import UserQuery
from app.queries.user_token_email_reply_query import UserTokenEmailReplyQuery
from app.services.message_service import MessageService
from speedup import buffered_randbytes


class UserTokenEmailReplyService:
    @staticmethod
    async def create_address(
        replying_user: User,
        mail_source: MailSource,
        *,
        reply_to_user_id: UserId | None = None,
    ) -> Email:
        """
        Create a new user email reply address.
        Replying user can use this address to send a message to the current user.
        """
        token = UserTokenStructUtils.to_str(
            await _create_token(
                replying_user, mail_source, reply_to_user_id=reply_to_user_id
            )
        )
        return Email(f'{token}@{SMTP_MESSAGES_FROM_HOST}')

    # TODO: limit size
    @staticmethod
    async def reply(reply_address: Email, subject: str, body: str) -> None:
        """Reply to a user with a message."""
        token = await UserTokenEmailReplyQuery.find_by_reply_address(reply_address)
        if token is None:
            raise_for.bad_user_token_struct()

        async with db(True) as conn:
            result = await conn.execute(
                """
                UPDATE user_token
                SET email_reply_usage_count = email_reply_usage_count + 1
                WHERE id = %s AND type = 'email_reply'
                AND email_reply_usage_count < %s
                """,
                (token['id'], EMAIL_REPLY_USAGE_LIMIT),
            )
            if not result.rowcount:
                logging.warning(
                    'UserTokenEmailReply usage limit exceeded for %d', token['id']
                )
                raise_for.bad_user_token_struct()

        user = await UserQuery.find_by_id(token['user_id'])
        assert user is not None, 'Token user must exist'

        with auth_context(user):
            await MessageService.send([token['email_reply_to_user_id']], subject, body)


async def _create_token(
    replying_user: User,
    mail_source: MailSource,
    *,
    reply_to_user_id: UserId | None = None,
) -> UserTokenStruct:
    """
    Create a new user email reply token.
    Replying user can use this token to send a message to the current user.
    """
    if reply_to_user_id is None:
        reply_to_user_id = auth_user(required=True)['id']

    user_id = replying_user['id']
    user_email_hashed = hash_bytes(replying_user['email'])
    token_bytes = buffered_randbytes(16)
    token_hashed = hash_bytes(token_bytes)

    token_id: UserTokenId = zid()  # type: ignore
    token_init: UserTokenEmailReplyInit = {
        'id': token_id,
        'type': 'email_reply',
        'user_id': user_id,
        'user_email_hashed': user_email_hashed,
        'token_hashed': token_hashed,
        'email_reply_source': mail_source,
        'email_reply_to_user_id': reply_to_user_id,
        'email_reply_usage_count': 0,
    }

    async with db(True) as conn:
        await conn.execute(
            """
            INSERT INTO user_token (
                id, type, user_id, user_email_hashed, token_hashed,
                email_reply_source, email_reply_to_user_id, email_reply_usage_count
            )
            VALUES (
                %(id)s, %(type)s, %(user_id)s, %(user_email_hashed)s, %(token_hashed)s,
                %(email_reply_source)s, %(email_reply_to_user_id)s, %(email_reply_usage_count)s
            )
            """,
            token_init,
        )

    return UserTokenStruct(id=token_id, token=token_bytes)
