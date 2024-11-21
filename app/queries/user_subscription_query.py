from sqlalchemy import select, text

from app.db import db
from app.lib.auth_context import auth_user
from app.models.db.user_subscription import UserSubscription, UserSubscriptionTarget


class UserSubscriptionQuery:
    @staticmethod
    async def is_subscribed(target: UserSubscriptionTarget, target_id: int) -> bool:
        """
        Check if the user is subscribed to the target.
        """
        async with db() as session:
            stmt = select(text('1')).where(
                UserSubscription.user_id == auth_user(required=True).id,
                UserSubscription.target == target,
                UserSubscription.target_id == target_id,
            )
            return await session.scalar(stmt) is not None
