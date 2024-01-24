from sqlalchemy import false, func, select

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
            stmt = (
                select(func.count())
                .select_from(
                    select(Message).where(
                        Message.to_user_id == user_id,
                        Message.to_hidden == false(),
                    )
                )
                .union(
                    select(func.count()).select_from(
                        select(Message).where(
                            Message.to_user_id == user_id,
                            Message.to_hidden == false(),
                            Message.is_read == false(),
                        )
                    )
                )
            )

            total, active = (await session.scalars(stmt)).all()
            return total, active

    @staticmethod
    async def count_sent_by_user_id(user_id: int) -> int:
        """
        Count sent messages by user id.
        """

        async with db() as session:
            stmt = select(func.count()).select_from(
                select(Message).where(
                    Message.from_user_id == user_id,
                    Message.from_hidden == false(),
                )
            )

            # TODO: test empty results
            return await session.scalar(stmt)
