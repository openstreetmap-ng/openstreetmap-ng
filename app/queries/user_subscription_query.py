from typing import Any

from app.db import db, db_fetchall, db_fetchcol
from app.lib.auth.context import auth_user
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

        user_id = user['id']
        async with (
            db() as conn,
            await conn.execute(t"""
                SELECT 1 FROM user_subscription
                WHERE target = {target} AND target_id = {target_id} AND user_id = {user_id}
                LIMIT 1
            """) as r,
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
        target_ids = list(id_map)
        user_id = user['id']

        target_ids_found: list[UserSubscriptionTargetId] = await db_fetchcol(
            int,
            t"""
                SELECT target_id FROM user_subscription
                WHERE target = {target} AND target_id = ANY({target_ids}) AND user_id = {user_id}
            """,
        )  # type: ignore[assignment]
        for target_id in target_ids_found:
            id_map[target_id][is_subscribed_key] = True

    @staticmethod
    async def get_subscribed_users(
        target: UserSubscriptionTarget, target_id: UserSubscriptionTargetId
    ) -> list[User]:
        """Get users subscribed to the target."""
        return await db_fetchall(
            User,
            t"""
                SELECT "user".* FROM "user"
                JOIN user_subscription s ON id = s.user_id
                WHERE s.target = {target} AND s.target_id = {target_id}
            """,
        )
