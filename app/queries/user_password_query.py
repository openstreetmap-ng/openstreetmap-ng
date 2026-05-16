from datetime import datetime

from app.db import db_fetchval
from app.models.types import UserId


class UserPasswordQuery:
    @staticmethod
    async def get_updated_at(user_id: UserId) -> datetime | None:
        """Get the updated_at timestamp of the user's password."""
        return await db_fetchval(
            datetime,
            t"""
                SELECT updated_at
                FROM user_password
                WHERE user_id = {user_id}
            """,
        )
