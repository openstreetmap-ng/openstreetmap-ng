from sqlalchemy import select

from db import DB
from models.db.user import User


class UserRepository:
    @staticmethod
    async def find_one_by_id(user_id: int) -> User | None:
        """
        Find a user by id.
        """

        async with DB() as session:
            return await session.get(User, user_id)

    @staticmethod
    async def find_one_by_display_name(display_name: str) -> User | None:
        """
        Find a user by display name.
        """

        async with DB() as session:
            stmt = select(User).where(User.display_name == display_name)

            return await session.scalar(stmt)
