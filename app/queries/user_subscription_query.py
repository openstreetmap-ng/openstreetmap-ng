from psycopg.rows import dict_row

from app.db import db
from app.lib.auth_context import auth_user
from app.models.db.user import User
from app.models.db.user_subscription import UserSubscriptionTarget
from app.models.types import UserSubscriptionTargetId


class UserSubscriptionQuery:
    @staticmethod
    async def is_subscribed(
        target: UserSubscriptionTarget, target_id: UserSubscriptionTargetId
    ) -> bool:
        """
        Check if the current user is subscribed to the target.
        If the user is not authenticated, returns False.
        """
        user = auth_user()
        if user is None:
            return False

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT 1 FROM user_subscription
                WHERE target = %s AND target_id = %s AND user_id = %s
                LIMIT 1
                """,
                (target, target_id, user['id']),
            ) as r,
        ):
            return await r.fetchone() is not None

    @staticmethod
    async def get_subscribed_users(
        target: UserSubscriptionTarget, target_id: UserSubscriptionTargetId
    ) -> list[User]:
        """Get users subscribed to the target."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT "user".* FROM "user"
                JOIN user_subscription s ON id = s.user_id
                WHERE s.target = %s AND s.target_id = %s
                """,
                (target, target_id),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore
