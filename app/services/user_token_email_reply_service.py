import logging

from zid import zid

from app.config import EMAIL_REPLY_USAGE_LIMIT, SMTP_MESSAGES_FROM_HOST
from app.db import db_insert, db_update
from app.exceptions.context import raise_for
from app.lib.auth import user_token
from app.lib.auth.context import auth_context, auth_user
from app.lib.auth.crypto import hash_bytes
from app.models.db.mail import MailSource
from app.models.db.user import User
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
    ):
        """
        Create a new user email reply address.
        Replying user can use this address to send a message to the current user.
        """
        token = user_token.encode(
            await _create_token(
                replying_user, mail_source, reply_to_user_id=reply_to_user_id
            )
        )
        return Email(f'{token}@{SMTP_MESSAGES_FROM_HOST}')

    # TODO: limit size
    @staticmethod
    async def reply(reply_address: Email, subject: str, body: str):
        """Reply to a user with a message."""
        token = await UserTokenEmailReplyQuery.find_by_reply_address(reply_address)
        if token is None:
            raise_for.bad_user_token_struct()

        token_id = token['id']
        rowcount = await db_update(
            'user_token',
            {'email_reply_usage_count': t'email_reply_usage_count + 1'},
            where=t"id = {token_id} AND type = 'email_reply' AND email_reply_usage_count < {EMAIL_REPLY_USAGE_LIMIT}",
        )
        if not rowcount:
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
):
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

    await db_insert(
        'user_token',
        {
            'id': token_id,
            'type': 'email_reply',
            'user_id': user_id,
            'user_email_hashed': user_email_hashed,
            'token_hashed': token_hashed,
            'email_reply_source': mail_source,
            'email_reply_to_user_id': reply_to_user_id,
            'email_reply_usage_count': 0,
        },
    )

    return UserTokenStruct(id=token_id, token=token_bytes)
