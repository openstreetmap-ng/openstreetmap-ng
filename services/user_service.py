from db import DB
from models.db.user import User


class UserService:
    @staticmethod
    async def find_one_by_id(user_id: int) -> User | None:
        """
        Find a user by id.
        """

        async with DB() as session:
            return await session.get(User, user_id)
