from collections.abc import Sequence

from sqlalchemy import select, text

from app.db import db
from app.lib.auth_context import auth_user
from app.models.db.user import User
from app.models.db.user_subscription import UserSubscription, UserSubscriptionTarget
from app.queries.user_query import UserQuery


class UserSubscriptionQuery:
    @staticmethod
    async def is_subscribed(target: UserSubscriptionTarget, target_id: int) -> bool:
        """
        Check if the current user is subscribed to the target.

        If the user is not authenticated, returns False.
        """
        current_user = auth_user()
        if current_user is None:
            return False
        async with db() as session:
            stmt = select(text('1')).where(
                UserSubscription.user_id == current_user.id,
                UserSubscription.target == target,
                UserSubscription.target_id == target_id,
            )
            return await session.scalar(stmt) is not None

    @staticmethod
    async def get_subscribed_users(target: UserSubscriptionTarget, target_id: int) -> Sequence[User]:
        """
        Get users subscribed to the target.
        """
        async with db() as session:
            stmt = select(UserSubscription.user_id).where(
                UserSubscription.target == target,
                UserSubscription.target_id == target_id,
            )
            user_ids = (await session.scalars(stmt)).all()
        return await UserQuery.find_many_by_ids(user_ids)
