import logging
from asyncio import TaskGroup
from datetime import datetime

from psycopg.sql import SQL
from psycopg.sql import Literal as PgLiteral
from zid import zid

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t, translation_context
from app.models.db.message import Message, MessageInit, messages_resolve_rich_text
from app.models.db.user import User
from app.models.types import DisplayName, MessageId, UserId
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery
from app.services.email_service import EmailService


class MessageService:
    @staticmethod
    async def send(
        recipients: list[DisplayName] | list[UserId], subject: str, body: str
    ) -> MessageId:
        """Send a message to a user."""
        assert recipients, 'Recipients must be set'

        if isinstance(recipients[0], str):
            to_users = await UserQuery.find_many_by_display_names(recipients)  # type: ignore
            if len(to_users) < len(recipients):
                not_found = set(recipients)
                not_found.difference_update(u['display_name'] for u in to_users)
                StandardFeedback.raise_error(
                    'recipient',
                    t('validation.user_not_found', user=repr(next(iter(not_found)))),
                )

            to_user_ids: list[UserId] = [u['id'] for u in to_users]
        else:
            to_user_ids = recipients  # type: ignore

        from_user = auth_user(required=True)
        from_user_id = from_user['id']
        if from_user_id in to_user_ids:
            StandardFeedback.raise_error(
                'recipient', t('validation.cant_send_message_to_self')
            )

        message_id: MessageId = zid()  # type: ignore
        message_init: MessageInit = {
            'id': message_id,
            'from_user_id': from_user_id,
            'subject': subject,
            'body': body,
        }

        async with db(True) as conn:
            async with await conn.execute(
                """
                INSERT INTO message (
                    id, from_user_id,
                    subject, body
                )
                VALUES (
                    %(id)s, %(from_user_id)s,
                    %(subject)s, %(body)s
                )
                RETURNING created_at
                """,
                message_init,
            ) as r:
                created_at: datetime = (await r.fetchone())[0]  # type: ignore

            await conn.execute(
                SQL("""
                INSERT INTO message_recipient (
                    message_id, user_id
                )
                VALUES {}
                """).format(
                    SQL(',').join(
                        SQL('({},%s)').format(PgLiteral(message_id)) * len(to_user_ids)
                    )
                ),
                to_user_ids,
            )

        logging.info(
            'Sent message %d from user %d to recipients %r with subject %r',
            message_id,
            from_user_id,
            recipients,
            subject,
        )

        message: Message = {
            'id': message_id,
            'from_user_id': from_user_id,
            'from_user_hidden': False,
            'subject': subject,
            'body': body,
            'body_rich_hash': None,
            'created_at': created_at,
            'from_user': from_user,  # type: ignore
        }

        await MessageQuery.resolve_recipients([message])
        await _send_activity_email(message)
        return message_id

    @staticmethod
    async def set_state(message_id: MessageId, *, read: bool) -> None:
        """Mark a message as read or unread."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            result = await conn.execute(
                """
                UPDATE message_recipient
                SET read = %s
                WHERE message_id = %s
                AND user_id = %s
                AND NOT hidden
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
            # Update sender if user is the sender
            await conn.execute(
                """
                UPDATE message SET from_user_hidden = TRUE
                WHERE id = %s AND from_user_id = %s AND NOT from_user_hidden
                """,
                (message_id, user_id),
            )

            # Update recipient if user is a recipient
            await conn.execute(
                """
                UPDATE message_recipient SET hidden = TRUE
                WHERE message_id = %s AND user_id = %s AND NOT hidden
                """,
                (message_id, user_id),
            )

            # Check if anyone still has access to the message
            async with await conn.execute(
                """
                SELECT 1 FROM message WHERE id = %s AND NOT from_user_hidden
                UNION ALL
                SELECT 1 FROM message_recipient WHERE message_id = %s AND NOT hidden
                LIMIT 1
                """,
                (message_id, message_id),
            ) as r:
                should_delete = await r.fetchone() is None

            # No one has access anymore - delete completely
            if should_delete:
                await conn.execute(
                    'DELETE FROM message_recipient WHERE message_id = %s',
                    (message_id,),
                )
                await conn.execute(
                    'DELETE FROM message WHERE id = %s',
                    (message_id,),
                )


async def _send_activity_email(message: Message) -> None:
    assert 'recipients' in message, 'Message recipients must be set'

    async with TaskGroup() as tg:
        tg.create_task(messages_resolve_rich_text([message]))
        tg.create_task(UserQuery.resolve_users(message['recipients'], kind=User))

    async with TaskGroup() as tg:
        for recipient in message['recipients']:
            to_user: User = recipient['user']  # type: ignore

            with translation_context(to_user['language']):
                subject = t(
                    'user_mailer.message_notification.subject',
                    message_title=message['subject'],
                )

            tg.create_task(
                EmailService.schedule(
                    source='message',
                    from_user_id=message['from_user_id'],
                    to_user=to_user,
                    subject=subject,
                    template_name='email/message',
                    template_data={'message': message},
                )
            )
