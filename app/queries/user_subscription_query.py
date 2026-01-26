from typing import Any

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
    ):
        """Check if the current user is subscribed to the target."""
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
    async def resolve_is_subscribed(
        target: UserSubscriptionTarget,
        items: list,
        *,
        id_key: str = 'id',
        is_subscribed_key: str = 'is_subscribed',
    ):
        if not items:
            return

        user = auth_user()
        if user is None:
            return

        id_map: dict[UserSubscriptionTargetId, Any] = {
            item[id_key]: item for item in items
        }

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT target_id FROM user_subscription
                WHERE target = %s AND target_id = ANY(%s) AND user_id = %s
                """,
                (target, list(id_map), user['id']),
            ) as r,
        ):
            rows: list[tuple[UserSubscriptionTargetId]] = await r.fetchall()
            for (target_id,) in rows:
                id_map[target_id][is_subscribed_key] = True

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
