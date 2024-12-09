import logging
from asyncio import TaskGroup

from sqlalchemy import and_, false, or_, select, update

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t, translation_context
from app.models.db.mail import MailSource
from app.models.db.message import Message
from app.models.types import DisplayNameType
from app.queries.user_query import UserQuery
from app.services.email_service import EmailService


class MessageService:
    @staticmethod
    async def send(recipient: DisplayNameType | int, subject: str, body: str) -> int:
        """
        Send a message to a user.
        """
        if isinstance(recipient, str):
            recipient_user = await UserQuery.find_one_by_display_name(recipient)
            if recipient_user is None:
                StandardFeedback.raise_error('recipient', t('validation.user_not_found'))
            recipient = recipient_user.id

        from_user = auth_user(required=True)
        if recipient == from_user.id:
            StandardFeedback.raise_error('recipient', t('validation.cant_send_message_to_self'))

        async with db_commit() as session:
            message = Message(
                from_user_id=from_user.id,
                to_user_id=recipient,
                subject=subject,
                body=body,
            )
            session.add(message)

        logging.info(
            'Sent message %d from user %d to recipient %r with subject %r',
            message.id,
            from_user.id,
            recipient,
            subject,
        )
        message.from_user = from_user
        await _send_activity_email(message)
        return message.id

    @staticmethod
    async def set_state(message_id: int, *, is_read: bool) -> None:
        """
        Mark a message as read or unread.
        """
        async with db_commit() as session:
            stmt = (
                update(Message)
                .where(
                    Message.id == message_id,
                    Message.to_user_id == auth_user(required=True).id,
                    Message.to_hidden == false(),
                )
                .values({Message.is_read: is_read})
                .inline()
            )
            await session.execute(stmt)

    @staticmethod
    async def delete_message(message_id: int) -> None:
        """
        Delete a message.
        """
        user_id = auth_user(required=True).id
        async with db_commit() as session:
            stmt = (
                select(Message)
                .where(
                    Message.id == message_id,
                    or_(
                        and_(
                            Message.from_user_id == user_id,
                            Message.from_hidden == false(),
                        ),
                        and_(
                            Message.to_user_id == user_id,
                            Message.to_hidden == false(),
                        ),
                    ),
                )
                .with_for_update()
            )
            message = await session.scalar(stmt)
            if message is None:
                return
            if message.from_user_id == user_id:
                message.from_hidden = True
            if message.to_user_id == user_id:
                message.to_hidden = True
            if message.from_hidden and message.to_hidden:
                await session.delete(message)


async def _send_activity_email(message: Message) -> None:
    async with TaskGroup() as tg:
        tg.create_task(message.resolve_rich_text())
        to_user = await UserQuery.find_one_by_id(message.to_user_id)
        if to_user is None:
            raise AssertionError('Recipient user must exist')

    with translation_context(to_user.language):
        subject = t('user_mailer.message_notification.subject', message_title=message.subject)
    await EmailService.schedule(
        source=MailSource.message,
        from_user=message.from_user,
        to_user=to_user,
        subject=subject,
        template_name='email/message.jinja2',
        template_data={'message': message},
    )
