import logging

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.models.db.user_subscription import UserSubscription, UserSubscriptionTarget


class UserSubscriptionService:
    @staticmethod
    async def subscribe(target: UserSubscriptionTarget, target_id: int) -> None:
        """
        Subscribe the user to the target.
        """
        user_id = auth_user(required=True).id
        async with db_commit() as session:
            stmt = (
                insert(UserSubscription)
                .values(
                    {
                        UserSubscription.user_id: user_id,
                        UserSubscription.target: target,
                        UserSubscription.target_id: target_id,
                    }
                )
                .on_conflict_do_nothing(
                    index_elements=(UserSubscription.target, UserSubscription.target_id, UserSubscription.user_id)
                )
                .inline()
            )
            await session.execute(stmt)
        logging.debug('Subscribed user[%d] to %s[%d]', user_id, target, target_id)

    @staticmethod
    async def unsubscribe(target: UserSubscriptionTarget, target_id: int) -> None:
        """
        Unsubscribe the user from the target.
        """
        user_id = auth_user(required=True).id
        async with db_commit() as session:
            stmt = delete(UserSubscription).where(
                UserSubscription.user_id == user_id,
                UserSubscription.target == target,
                UserSubscription.target_id == target_id,
            )
            await session.execute(stmt)
        logging.debug('Unsubscribed user[%d] from %s[%d]', user_id, target, target_id)
