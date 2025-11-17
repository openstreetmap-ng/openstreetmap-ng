from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.sql import SQL

from app.db import db
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
        async with (
            db(conn) as conn,
            await conn.cursor(row_factory=dict_row).execute(
                SQL("""
                    SELECT * FROM user_totp
                    WHERE user_id = %s
                    {}
                """).format(SQL('FOR UPDATE' if not conn.read_only else '')),
                (user_id,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore
