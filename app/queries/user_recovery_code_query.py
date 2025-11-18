from psycopg import AsyncConnection

from app.db import db
from app.models.types import UserId


class UserRecoveryCodeQuery:
    @staticmethod
    async def count_remaining_codes(
        user_id: UserId,
        *,
        conn: AsyncConnection | None = None,
    ) -> int:
        """Count unused recovery codes for a user in the current batch."""
        async with (
            db(conn) as conn,
            await conn.execute(
                """
                SELECT 8 - COUNT(*) FROM user_recovery_code_used WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            return (await r.fetchone())[0]  # type: ignore
