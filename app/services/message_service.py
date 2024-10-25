import logging

from sqlalchemy import and_, false, or_, select, update

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.message_collector import MessageCollector
from app.lib.translation import t
from app.models.db.message import Message
from app.models.types import DisplayNameType
from app.queries.user_query import UserQuery


class MessageService:
    @staticmethod
    async def send(recipient: DisplayNameType | int, subject: str, body: str) -> int:
        """
        Send a message to a user.
        """
        if isinstance(recipient, str):
            recipient_user = await UserQuery.find_one_by_display_name(recipient)
            if recipient_user is None:
                MessageCollector.raise_error('recipient', t('validation.user_not_found'))
            recipient = recipient_user.id

        from_user_id = auth_user(required=True).id
        if recipient == from_user_id:
            MessageCollector.raise_error('recipient', t('validation.cant_send_message_to_self'))

        async with db_commit() as session:
            message = Message(
                from_user_id=from_user_id,
                to_user_id=recipient,
                subject=subject,
                body=body,
            )
            session.add(message)
        logging.info(
            'Sent message %d from user %d to recipient %r with subject %r',
            message.id,
            message.from_user_id,
            recipient,
            subject,
        )
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
