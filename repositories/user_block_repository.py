from sqlalchemy import false, func, select

from db import DB
from models.db.user_block import UserBlock


class UserBlockRepository:
    @staticmethod
    async def count_received_by_user_id(user_id: int) -> tuple[int, int]:
        """
        Count received blocks by user id.

        Returns a tuple of (total, active).
        """

        async with DB() as session:
            stmt = (
                select(func.count())
                .select_from(
                    select(UserBlock).where(
                        UserBlock.to_user_id == user_id,
                    )
                )
                .union(
                    select(func.count()).select_from(
                        select(UserBlock).where(
                            UserBlock.to_user_id == user_id,
                            UserBlock.expired == false(),
                        )
                    )
                )
            )

            total, active = (await session.scalars(stmt)).all()
            return total, active

    @staticmethod
    async def count_given_by_user_id(user_id: int) -> tuple[int, int]:
        """
        Count given blocks by user id.

        Returns a tuple of (total, active).
        """

        async with DB() as session:
            stmt = (
                select(func.count())
                .select_from(
                    select(UserBlock).where(
                        UserBlock.from_user_id == user_id,
                    )
                )
                .union(
                    select(func.count()).select_from(
                        select(UserBlock).where(
                            UserBlock.from_user_id == user_id,
                            UserBlock.expired == false(),
                        )
                    )
                )
            )

            total, active = (await session.scalars(stmt)).all()
            return total, active
