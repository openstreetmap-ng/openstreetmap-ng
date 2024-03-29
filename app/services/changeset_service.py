import logging

from sqlalchemy import func, select

from app.db import db_autocommit
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.statement_context import apply_statement_context
from app.models.db.changeset import Changeset
from app.models.db.changeset_subscription import ChangesetSubscription


class ChangesetService:
    @staticmethod
    async def create(tags: dict[str, str]) -> int:
        """
        Create a new changeset and return its id.
        """
        user_id = auth_user().id

        async with db_autocommit() as session:
            changeset = Changeset(
                user_id=user_id,
                tags=tags,
            )
            session.add(changeset)
            await session.flush()

            # TODO: test subscribed
            changeset_id = changeset.id
            subscription = ChangesetSubscription(
                user_id=user_id,
                changeset_id=changeset_id,
            )
            session.add(subscription)

            logging.debug('Created changeset %d for user %d', changeset_id, user_id)
            return changeset_id

    @staticmethod
    async def update_tags(changeset_id: int, tags: dict[str, str]) -> None:
        """
        Update changeset tags.
        """
        async with db_autocommit() as session:
            stmt = select(Changeset).where(Changeset.id == changeset_id).with_for_update()
            stmt = apply_statement_context(stmt)
            changeset = await session.scalar(stmt)

            if changeset is None:
                raise_for().changeset_not_found(changeset_id)
            if changeset.user_id != auth_user().id:
                raise_for().changeset_access_denied()
            if changeset.closed_at is not None:
                raise_for().changeset_already_closed(changeset_id, changeset.closed_at)

            changeset.tags = tags

    @staticmethod
    async def close(changeset_id: int) -> None:
        """
        Close a changeset.
        """
        async with db_autocommit() as session:
            stmt = select(Changeset).where(Changeset.id == changeset_id).with_for_update()
            stmt = apply_statement_context(stmt)
            changeset = await session.scalar(stmt)

            if changeset is None:
                raise_for().changeset_not_found(changeset_id)
            if changeset.user_id != auth_user().id:
                raise_for().changeset_access_denied()
            if changeset.closed_at is not None:
                raise_for().changeset_already_closed(changeset_id, changeset.closed_at)

            changeset.closed_at = func.statement_timestamp()
