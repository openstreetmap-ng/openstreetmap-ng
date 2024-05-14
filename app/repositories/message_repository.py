from sqlalchemy import false, func, select, text

from app.db import db
from app.models.db.message import Message


class MessageRepository:
    @staticmethod
    async def count_received_by_user_id(user_id: int) -> tuple[int, int]:
        """
        Count received messages by user id.

        Returns a tuple of (total, unread).
        """

        async with db() as session:
            stmt_total = select(func.count()).select_from(
                select(text('1')).where(
                    Message.to_user_id == user_id,
                    Message.to_hidden == false(),
                )
            )
            stmt_unread = select(func.count()).select_from(
                select(text('1')).where(
                    Message.to_user_id == user_id,
                    Message.to_hidden == false(),
                    Message.is_read == false(),
                )
            )
            stmt = stmt_total.union_all(stmt_unread)

            total, unread = (await session.scalars(stmt)).all()
            return total, unread

    @staticmethod
    async def count_sent_by_user_id(user_id: int) -> int:
        """
        Count sent messages by user id.
        """

        async with db() as session:
            stmt = select(func.count()).select_from(
                select(text('1')).where(
                    Message.from_user_id == user_id,
                    Message.from_hidden == false(),
                )
            )

            # TODO: test empty results
            return await session.scalar(stmt)
