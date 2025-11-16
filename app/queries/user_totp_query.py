"""User TOTP query operations."""

from asyncpg import Connection

from app.db import db
from app.lib.auth_context import auth_user
from app.models.db.user_totp import UserTOTP
from app.models.types import UserId


class UserTOTPQuery:
    """User TOTP query operations."""

    @staticmethod
    async def find_one_by_user_id(
        user_id: UserId,
        *,
        conn: Connection | None = None,
    ) -> UserTOTP | None:
        """Find TOTP credentials for a user."""
        async with db(read_only=True, conn=conn) as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM user_totp
                WHERE user_id = $1
                """,
                user_id,
            )
            return dict(row) if row else None

    @staticmethod
    async def find_one_by_current_user(
        *,
        conn: Connection | None = None,
    ) -> UserTOTP | None:
        """Find TOTP credentials for the current authenticated user."""
        user = auth_user(required=True)
        return await UserTOTPQuery.find_one_by_user_id(user['id'], conn=conn)

    @staticmethod
    async def has_totp(user_id: UserId, *, conn: Connection | None = None) -> bool:
        """Check if a user has TOTP enabled."""
        async with db(read_only=True, conn=conn) as conn:
            result = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM user_totp WHERE user_id = $1
                )
                """,
                user_id,
            )
            return bool(result)
