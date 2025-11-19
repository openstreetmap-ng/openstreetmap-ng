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
        """Count unused recovery codes for a user."""
        async with (
            db(conn) as conn,
            await conn.execute(
                """
                SELECT cardinality(array_remove(codes_hashed, NULL))
                FROM user_recovery_code
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            row = await r.fetchone()
            return row[0] if row is not None else 0
