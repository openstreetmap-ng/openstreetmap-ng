from psycopg import AsyncConnection

from app.db import db_fetchone
from app.models.db.user_totp import UserTOTP
from app.models.types import UserId


class UserTOTPQuery:
    @staticmethod
    async def find_one_by_user_id(
        user_id: UserId,
        *,
        conn: AsyncConnection | None = None,
    ) -> UserTOTP | None:
        """Find TOTP credentials for a user, for update."""
        return await db_fetchone(
            UserTOTP,
            t'SELECT * FROM user_totp WHERE user_id = {user_id}',
            for_update=True,
            conn=conn,
        )
