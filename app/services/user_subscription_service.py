import logging

from app.db import db_delete, db_insert
from app.lib.auth.context import auth_user
from app.models.db.user_subscription import UserSubscriptionTarget
from app.models.types import UserId, UserSubscriptionTargetId


class UserSubscriptionService:
    @staticmethod
    async def subscribe(
        target: UserSubscriptionTarget, target_id: UserSubscriptionTargetId
    ):
        """Subscribe the user to the target."""
        user_id = auth_user(required=True)['id']

        await db_insert(
            'user_subscription',
            {'user_id': user_id, 'target': target, 'target_id': target_id},
            on_conflict=t'DO NOTHING',
        )

        logging.debug('Subscribed user %d to %s/%d', user_id, target, target_id)

    @staticmethod
    async def unsubscribe(
        target: UserSubscriptionTarget,
        target_id: UserSubscriptionTargetId,
        *,
        user_id: UserId | None = None,
    ):
        """Unsubscribe the user from the target."""
        if user_id is None:
            user_id = auth_user(required=True)['id']

        await db_delete(
            'user_subscription',
            where={'user_id': user_id, 'target': target, 'target_id': target_id},
        )

        logging.debug('Unsubscribed user %d from %s/%d', user_id, target, target_id)
