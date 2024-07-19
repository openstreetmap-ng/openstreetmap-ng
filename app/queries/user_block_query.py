from sqlalchemy import false, func, select, text

from app.db import db
from app.models.db.user_block import UserBlock


class UserBlockQuery:
    @staticmethod
    async def count_received_by_user_id(user_id: int) -> tuple[int, int]:
        """
        Count received blocks by user id.

        Returns a tuple of (total, active).
        """
        async with db() as session:
            stmt_total = select(func.count()).select_from(
                select(text('1'))
                .where(
                    UserBlock.to_user_id == user_id,
                )
                .subquery()
            )
            stmt_active = select(func.count()).select_from(
                select(text('1'))
                .where(
                    UserBlock.to_user_id == user_id,
                    UserBlock.expired == false(),
                )
                .subquery()
            )
            stmt = stmt_total.union_all(stmt_active)
            total, active = (await session.scalars(stmt)).all()
            return total, active

    @staticmethod
    async def count_given_by_user_id(user_id: int) -> tuple[int, int]:
        """
        Count given blocks by user id.

        Returns a tuple of (total, active).
        """
        async with db() as session:
            stmt_total = select(func.count()).select_from(
                select(text('1'))
                .where(
                    UserBlock.from_user_id == user_id,
                )
                .subquery()
            )
            stmt_active = select(func.count()).select_from(
                select(text('1'))
                .where(
                    UserBlock.from_user_id == user_id,
                    UserBlock.expired == false(),
                )
                .subquery()
            )
            stmt = stmt_total.union_all(stmt_active)
            total, active = (await session.scalars(stmt)).all()
            return total, active
