from sqlalchemy import select, text

from app.db import db
from app.lib.auth_context import auth_user
from app.models.db.changeset_subscription import ChangesetSubscription


class ChangesetSubscriptionQuery:
    @staticmethod
    async def is_subscribed(changeset_id: int) -> bool:
        """
        Check if the user is subscribed to the changeset.
        """
        async with db() as session:
            stmt = select(text('1')).where(
                ChangesetSubscription.changeset_id == changeset_id,
                ChangesetSubscription.user_id == auth_user().id,
            )
            return await session.scalar(stmt) is not None
