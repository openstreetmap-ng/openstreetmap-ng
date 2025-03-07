import logging

from app.db import db2
from app.lib.auth_context import auth_user
from app.models.db.user_subscription import UserSubscriptionTarget, UserSubscriptionTargetId


class UserSubscriptionService:
    @staticmethod
    async def subscribe(target: UserSubscriptionTarget, target_id: UserSubscriptionTargetId) -> None:
        """Subscribe the user to the target."""
        user_id = auth_user(required=True)['id']

        async with db2(True) as conn:
            await conn.execute(
                """
                INSERT INTO user_subscription (user_id, target, target_id)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (user_id, target, target_id),
            )

        logging.debug('Subscribed user %d to %s/%d', user_id, target, target_id)

    @staticmethod
    async def unsubscribe(target: UserSubscriptionTarget, target_id: UserSubscriptionTargetId) -> None:
        """Unsubscribe the user from the target."""
        user_id = auth_user(required=True)['id']

        async with db2(True) as conn:
            await conn.execute(
                """
                DELETE FROM user_subscription
                WHERE user_id = %s AND target = %s AND target_id = %s
                """,
                (user_id, target, target_id),
            )

        logging.debug('Unsubscribed user %d from %s/%d', user_id, target, target_id)
