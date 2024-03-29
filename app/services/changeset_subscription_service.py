import logging

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.db import db_autocommit
from app.lib.auth_context import auth_user
from app.models.db.changeset_subscription import ChangesetSubscription


class ChangesetSubscriptionService:
    @staticmethod
    async def subscribe(changeset_id: int) -> None:
        """
        Subscribe the current user to the changeset.
        """
        user_id = auth_user().id
        logging.debug('Subscribing user %d to changeset %d', user_id, changeset_id)

        async with db_autocommit() as session:
            stmt = (
                insert(ChangesetSubscription)
                .values(
                    {
                        ChangesetSubscription.changeset_id: changeset_id,
                        ChangesetSubscription.user_id: user_id,
                    }
                )
                .on_conflict_do_nothing(
                    index_elements=(ChangesetSubscription.changeset_id, ChangesetSubscription.user_id),
                )
            )

            await session.execute(stmt)

    @staticmethod
    async def unsubscribe(changeset_id: int) -> None:
        """
        Unsubscribe the current user from the changeset.
        """
        user_id = auth_user().id
        logging.debug('Unsubscribing user %d from changeset %d', user_id, changeset_id)

        async with db_autocommit() as session:
            stmt = delete(ChangesetSubscription).where(
                ChangesetSubscription.changeset_id == changeset_id,
                ChangesetSubscription.user_id == user_id,
            )

            await session.execute(stmt)
