from datetime import datetime

from app.db import db
from app.models.types import UserId


class UserPasswordQuery:
    @staticmethod
    async def get_updated_at(user_id: UserId) -> datetime | None:
        """Get the updated_at timestamp of the user's password."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT updated_at
                FROM user_password
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            row: tuple[datetime] | None = await r.fetchone()
            return row[0] if row is not None else None
