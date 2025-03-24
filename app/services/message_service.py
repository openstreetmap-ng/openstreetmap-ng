import logging
from asyncio import TaskGroup
from datetime import datetime

from zid import zid

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t, translation_context
from app.models.db.message import Message, MessageInit, messages_resolve_rich_text
from app.models.types import DisplayName, MessageId, UserId
from app.queries.user_query import UserQuery
from app.services.email_service import EmailService


class MessageService:
    @staticmethod
    async def send(recipient: DisplayName | UserId, subject: str, body: str) -> MessageId:
        """Send a message to a user."""
        recipient_id: UserId
        if isinstance(recipient, str):
            recipient_user = await UserQuery.find_one_by_display_name(recipient)
            if recipient_user is None:
                StandardFeedback.raise_error('recipient', t('validation.user_not_found'))
            recipient_id = recipient_user['id']
        else:
            recipient_id = recipient

        from_user = auth_user(required=True)
        from_user_id = from_user['id']
        if recipient_id == from_user_id:
            StandardFeedback.raise_error('recipient', t('validation.cant_send_message_to_self'))

        message_id: MessageId = zid()  # type: ignore
        message_init: MessageInit = {
            'id': message_id,
            'from_user_id': from_user_id,
            'to_user_id': recipient_id,
            'subject': subject,
            'body': body,
        }

        async with (
            db(True) as conn,
            await conn.execute(
                """
                INSERT INTO message (
                    from_user_id, to_user_id, subject, body
                )
                VALUES (
                    %(from_user_id)s, %(to_user_id)s, %(subject)s, %(body)s
                )
                RETURNING created_at
                """,
                message_init,
            ) as r,
        ):
            created_at: datetime = (await r.fetchone())[0]  # type: ignore

        logging.info(
            'Sent message %d from user %d to recipient %r with subject %r',
            message_id,
            from_user_id,
            recipient_id,
            subject,
        )

        message: Message = {
            'id': message_id,
            'from_user_id': from_user_id,
            'from_user_hidden': False,
            'to_user_id': recipient_id,
            'to_user_hidden': False,
            'read': False,
            'subject': subject,
            'body': body,
            'body_rich_hash': None,
            'created_at': created_at,
            'from_user': from_user,  # type: ignore
        }

        await _send_activity_email(message)
        return message_id

    @staticmethod
    async def set_state(message_id: MessageId, *, read: bool) -> None:
        """Mark a message as read or unread."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            result = await conn.execute(
                """
                UPDATE message
                SET read = %s
                WHERE id = %s
                AND to_user_id = %s
                AND NOT to_user_hidden
                """,
                (read, message_id, user_id),
            )

            if not result.rowcount:
                raise_for.message_not_found(message_id)

    @staticmethod
    async def delete_message(message_id: MessageId) -> None:
        """Delete a message."""
        # TODO: account delete, prune messages
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT from_user_id, from_user_hidden, to_user_id, to_user_hidden
                FROM message
                WHERE id = %s
                AND (
                    (from_user_id = %s AND NOT from_user_hidden)
                    OR (to_user_id = %s AND NOT to_user_hidden)
                )
                FOR UPDATE
                """,
                (message_id, user_id, user_id),
            ) as r:
                row = await r.fetchone()
                if row is None:
                    return  # Message not found or already hidden

                from_user_id: UserId
                from_user_hidden: bool
                to_user_id: UserId
                to_user_hidden: bool
                from_user_id, from_user_hidden, to_user_id, to_user_hidden = row

            # Update flags based on which user is deleting
            if from_user_id == user_id:
                from_user_hidden = True
            if to_user_id == user_id:
                to_user_hidden = True

            # If both users have hidden the message, delete it completely
            if from_user_hidden and to_user_hidden:
                await conn.execute('DELETE FROM message WHERE id = %s', (message_id,))
                return

            # Otherwise, update the hidden flags
            await conn.execute(
                """
                UPDATE message
                SET from_user_hidden = %s, to_user_hidden = %s
                WHERE id = %s
                """,
                (from_user_hidden, to_user_hidden, message_id),
            )


async def _send_activity_email(message: Message) -> None:
    async with TaskGroup() as tg:
        tg.create_task(messages_resolve_rich_text([message]))
        to_user = await UserQuery.find_one_by_id(message['to_user_id'])
        assert to_user is not None, f'Recipient user {message["to_user_id"]} must exist'

    with translation_context(to_user['language']):
        subject = t('user_mailer.message_notification.subject', message_title=message['subject'])

    await EmailService.schedule(
        source='message',
        from_user_id=message['from_user_id'],
        to_user=to_user,
        subject=subject,
        template_name='email/message.jinja2',
        template_data={'message': message},
    )
