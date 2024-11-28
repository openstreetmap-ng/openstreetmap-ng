from collections.abc import Sequence

from sqlalchemy import and_, false, func, or_, select, text

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.options_context import apply_options_context
from app.models.db.message import Message


class MessageQuery:
    @staticmethod
    async def get_message_by_id(message_id: int) -> Message:
        """
        Get a message by id.
        """
        user_id = auth_user(required=True).id
        async with db() as session:
            stmt = select(Message).where(
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
            stmt = apply_options_context(stmt)
            message = await session.scalar(stmt)
            if message is None:
                raise_for.message_not_found(message_id)
            return message

    @staticmethod
    async def get_messages(
        *,
        inbox: bool,
        after: int | None = None,
        before: int | None = None,
        limit: int,
    ) -> Sequence[Message]:
        """
        Get user messages.
        """
        async with db() as session:
            stmt = select(Message)
            where_and = []

            if inbox:
                where_and.append(Message.to_user_id == auth_user(required=True).id)
                where_and.append(Message.to_hidden == false())
            else:
                where_and.append(Message.from_user_id == auth_user(required=True).id)
                where_and.append(Message.from_hidden == false())

            if after is not None:
                where_and.append(Message.id > after)
            if before is not None:
                where_and.append(Message.id < before)

            stmt = stmt.where(*where_and)
            order_desc = (after is None) or (before is not None)
            stmt = stmt.order_by(Message.id.desc() if order_desc else Message.id.asc()).limit(limit)

            stmt = apply_options_context(stmt)
            messages = (await session.scalars(stmt)).all()
            return messages if order_desc else messages[::-1]

    @staticmethod
    async def count_unread_received_messages() -> int:
        """
        Count all unread received messages for the current user.
        """
        async with db() as session:
            stmt = select(func.count()).select_from(
                select(text('1'))
                .where(
                    Message.to_user_id == auth_user(required=True).id,
                    Message.to_hidden == false(),
                    Message.is_read == false(),
                )
                .subquery()
            )
            return (await session.execute(stmt)).scalar_one()

    @staticmethod
    async def count_unread() -> int:
        """
        Count currently unread messages.
        """
        async with db() as session:
            stmt = select(func.count()).select_from(
                select(text('1'))
                .where(
                    Message.to_user_id == auth_user(required=True).id,
                    Message.to_hidden == false(),
                    Message.is_read == false(),
                )
                .subquery()
            )
            return (await session.execute(stmt)).scalar_one()

    @staticmethod
    async def count_by_user_id(user_id: int) -> tuple[int, int, int]:
        """
        Count received messages by user id.

        Returns a tuple of (total, unread, sent).
        """
        async with db() as session:
            stmt_total = select(func.count()).select_from(
                select(text('1'))
                .where(
                    Message.to_user_id == user_id,
                    Message.to_hidden == false(),
                )
                .subquery()
            )
            stmt_unread = select(func.count()).select_from(
                select(text('1'))
                .where(
                    Message.to_user_id == user_id,
                    Message.to_hidden == false(),
                    Message.is_read == false(),
                )
                .subquery()
            )
            stmt_sent = select(func.count()).select_from(
                select(text('1'))
                .where(
                    Message.from_user_id == user_id,
                    Message.from_hidden == false(),
                )
                .subquery()
            )
            stmt = stmt_total.union_all(stmt_unread, stmt_sent)
            total, unread, sent = (await session.scalars(stmt)).all()
            return total, unread, sent
