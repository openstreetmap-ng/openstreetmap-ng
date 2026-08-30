import logging
from asyncio import TaskGroup
from datetime import datetime
from typing import Literal

from zid import zid

from app.config import MESSAGE_RECIPIENTS_LIMIT
from app.db import (
    db,
    db_delete,
    db_fetchval,
    db_insert,
    db_insert_many,
    db_update,
)
from app.exceptions.context import raise_for
from app.lib.audit import audit
from app.lib.auth.context import auth_user
from app.lib.standard.feedback import StandardFeedback
from app.lib.text.translation import t, translation_context
from app.models.db.message import Message, messages_resolve_rich_text
from app.models.db.user import User
from app.models.types import DisplayName, MessageId, UserId
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery
from app.services.email_service import EmailService


class MessageService:
    @staticmethod
    async def send(
        recipients: list[DisplayName] | list[UserId], subject: str, body: str
    ):
        """Send a message to a user."""
        assert recipients, 'Recipients must be set'
        assert len(recipients) <= MESSAGE_RECIPIENTS_LIMIT, 'Too many recipients'

        if isinstance(recipients[0], str):
            to_users = await UserQuery.find_by_display_names(recipients)  # type: ignore
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

        async with db(True) as conn:
            row = await db_insert(
                'message',
                {
                    'id': message_id,
                    'from_user_id': from_user_id,
                    'subject': subject,
                    'body': body,
                },
                returning='created_at',
                conn=conn,
            )
            created_at: datetime = row[0]

            await db_insert_many(
                'message_recipient',
                [{'message_id': message_id, 'user_id': uid} for uid in to_user_ids],
                conn=conn,
            )

            async with conn.pipeline():
                for to_user_id in to_user_ids:
                    await audit(
                        'send_message',
                        conn,
                        target_user_id=to_user_id,
                        extra={'subject': subject},
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

        await MessageQuery.resolve_recipients(None, [message])
        await _send_activity_email(message)
        return message_id

    @staticmethod
    async def set_state(message_id: MessageId, *, read: bool):
        """Mark a message as read or unread."""
        user_id = auth_user(required=True)['id']

        rowcount = await db_update(
            'message_recipient',
            {'read': read},
            where=t"""message_id = {message_id}
                  AND user_id = {user_id}
                  AND read != {read}
                  AND NOT hidden""",
        )
        return bool(rowcount)

    @staticmethod
    async def delete_message(message_id: MessageId):
        """Delete a message."""
        # TODO: account delete, prune messages
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            # Get sender and lock message
            from_user_id = await db_fetchval(
                UserId,
                t'SELECT from_user_id FROM message WHERE id = {message_id}',
                for_update=True,
                conn=conn,
            )
            if from_user_id is None:
                raise_for.message_not_found(message_id)

            # Update sender if user is the sender
            if from_user_id == user_id:
                await db_update(
                    'message',
                    {'from_user_hidden': True},
                    where=t'id = {message_id} AND NOT from_user_hidden',
                    conn=conn,
                )
            # Update recipient if user is a recipient
            else:
                await db_update(
                    'message_recipient',
                    {'hidden': True},
                    where=t'message_id = {message_id} AND user_id = {user_id} AND NOT hidden',
                    conn=conn,
                )

            # Check if anyone still has access to the message
            still_visible = await db_fetchval(
                int,
                t"""
                    SELECT 1 FROM message WHERE id = {message_id} AND NOT from_user_hidden
                    UNION ALL
                    SELECT 1 FROM message_recipient WHERE message_id = {message_id} AND NOT hidden
                    LIMIT 1
                """,
                conn=conn,
            )

            # No one has access anymore - delete completely
            if still_visible is None:
                await db_delete('message', where={'id': message_id}, conn=conn)
                # message_recipient is deleted by cascade

    @staticmethod
    async def delete_older_than(
        *,
        inbox: bool,
        count: int,
        unit: Literal['days', 'weeks', 'months', 'years'],
    ) -> int:
        """Delete current user's messages older than a relative age."""
        user_id = auth_user(required=True)['id']
        interval_kw = SQL(unit)
        cutoff = SQL('statement_timestamp() - make_interval({} => %(count)s)').format(
            interval_kw
        )

        async with db(True) as conn:
            if inbox:
                query = SQL("""
                    WITH hidden AS (
                        UPDATE message_recipient AS mr
                        SET hidden = TRUE
                        FROM message AS m
                        WHERE mr.message_id = m.id
                          AND mr.user_id = %(user_id)s
                          AND NOT mr.hidden
                          AND m.created_at < {cutoff}
                        RETURNING mr.message_id
                    ),
                    cleanup AS (
                        DELETE FROM message AS m
                        WHERE m.id IN (SELECT message_id FROM hidden)
                          AND m.from_user_hidden
                          AND NOT EXISTS (
                              SELECT 1
                              FROM message_recipient AS mr
                              WHERE mr.message_id = m.id
                                AND NOT mr.hidden
                          )
                    )
                    SELECT COUNT(*) FROM hidden
                """).format(cutoff=cutoff)
            else:
                query = SQL("""
                    WITH hidden AS (
                        UPDATE message
                        SET from_user_hidden = TRUE
                        WHERE from_user_id = %(user_id)s
                          AND NOT from_user_hidden
                          AND created_at < {cutoff}
                        RETURNING id AS message_id
                    ),
                    cleanup AS (
                        DELETE FROM message AS m
                        WHERE m.id IN (SELECT message_id FROM hidden)
                          AND m.from_user_hidden
                          AND NOT EXISTS (
                              SELECT 1
                              FROM message_recipient AS mr
                              WHERE mr.message_id = m.id
                                AND NOT mr.hidden
                          )
                    )
                    SELECT COUNT(*) FROM hidden
                """).format(cutoff=cutoff)

            async with await conn.execute(
                query,
                {'user_id': user_id, 'count': count},
            ) as r:
                return (await r.fetchone())[0]  # type: ignore


async def _send_activity_email(message: Message):
    assert 'recipients' in message, 'Message recipients must be set'

    async with TaskGroup() as tg:
        tg.create_task(messages_resolve_rich_text([message]))
        tg.create_task(UserQuery.resolve_users(message['recipients'], kind=User))

    async with TaskGroup() as tg:
        num_others = len(message['recipients']) - 1
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
                    template_data={'message': message, 'num_others': num_others},
                )
            )
