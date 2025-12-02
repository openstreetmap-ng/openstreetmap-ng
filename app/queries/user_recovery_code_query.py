from datetime import datetime
from typing import TypedDict

from psycopg.rows import dict_row

from app.db import db
from app.models.types import UserId


class _RecoveryCodeStatus(TypedDict):
    num_remaining: int
    created_at: datetime | None


class UserRecoveryCodeQuery:
    @staticmethod
    async def check_any_by_user_id(user_id: UserId) -> bool:
        """Check if user has any unused recovery codes."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT 1
                FROM user_recovery_code
                WHERE user_id = %s
                  AND array_remove(codes_hashed, NULL) != '{}'
                """,
                (user_id,),
            ) as r,
        ):
            return await r.fetchone() is not None

    @staticmethod
    async def get_status(user_id: UserId) -> _RecoveryCodeStatus:
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT
                    cardinality(array_remove(codes_hashed, NULL)) AS num_remaining,
                    created_at
                FROM user_recovery_code
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            return await r.fetchone() or {'num_remaining': 0, 'created_at': None}  # type: ignore
