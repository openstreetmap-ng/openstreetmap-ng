from datetime import datetime
from typing import TypedDict

from app.db import db_fetchone, db_fetchval
from app.models.types import UserId


class _RecoveryCodeStatus(TypedDict):
    num_remaining: int
    created_at: datetime | None


class UserRecoveryCodeQuery:
    @staticmethod
    async def check_any_by_user_id(user_id: UserId):
        """Check if user has any unused recovery codes."""
        return (
            await db_fetchval(
                int,
                t"""
                    SELECT 1
                    FROM user_recovery_code
                    WHERE user_id = {user_id}
                      AND array_remove(codes_hashed, NULL) != '{{}}'
                """,
            )
        ) is not None

    @staticmethod
    async def get_status(user_id: UserId) -> _RecoveryCodeStatus:
        return (
            await db_fetchone(
                _RecoveryCodeStatus,
                t"""
                    SELECT
                        cardinality(array_remove(codes_hashed, NULL)) AS num_remaining,
                        created_at
                    FROM user_recovery_code
                    WHERE user_id = {user_id}
                """,
            )
        ) or {'num_remaining': 0, 'created_at': None}
