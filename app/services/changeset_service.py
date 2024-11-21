import logging

from sqlalchemy import and_, delete, func, null, or_, select, update
from sqlalchemy.orm import load_only

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.limits import CHANGESET_EMPTY_DELETE_TIMEOUT, CHANGESET_IDLE_TIMEOUT, CHANGESET_OPEN_TIMEOUT
from app.models.db.changeset import Changeset
from app.models.db.user_subscription import UserSubscriptionTarget
from app.services.user_subscription_service import UserSubscriptionService


class ChangesetService:
    @staticmethod
    async def create(tags: dict[str, str]) -> int:
        """
        Create a new changeset and return its id.
        """
        user_id = auth_user(required=True).id
        async with db_commit() as session:
            changeset = Changeset(
                user_id=user_id,
                tags=tags,
            )
            session.add(changeset)
        changeset_id = changeset.id
        logging.debug('Created changeset %d by user %d', changeset_id, user_id)
        await UserSubscriptionService.subscribe(UserSubscriptionTarget.changeset, changeset_id)
        return changeset_id

    @staticmethod
    async def update_tags(changeset_id: int, tags: dict[str, str]) -> None:
        """
        Update changeset tags.
        """
        async with db_commit() as session:
            stmt = (
                select(Changeset)
                .options(load_only(Changeset.id, Changeset.user_id, Changeset.closed_at))
                .where(Changeset.id == changeset_id)
                .with_for_update()
            )
            changeset = await session.scalar(stmt)

            if changeset is None:
                raise_for().changeset_not_found(changeset_id)
            if changeset.user_id != auth_user(required=True).id:
                raise_for().changeset_access_denied()
            if changeset.closed_at is not None:
                raise_for().changeset_already_closed(changeset_id, changeset.closed_at)

            changeset.tags = tags

    @staticmethod
    async def close(changeset_id: int) -> None:
        """
        Close a changeset.
        """
        async with db_commit() as session:
            stmt = (
                select(Changeset)
                .options(load_only(Changeset.id, Changeset.user_id, Changeset.closed_at))
                .where(Changeset.id == changeset_id)
                .with_for_update()
            )
            changeset = await session.scalar(stmt)

            if changeset is None:
                raise_for().changeset_not_found(changeset_id)
            if changeset.user_id != auth_user(required=True).id:
                raise_for().changeset_access_denied()
            if changeset.closed_at is not None:
                raise_for().changeset_already_closed(changeset_id, changeset.closed_at)

            changeset.closed_at = func.statement_timestamp()

    @staticmethod
    async def close_inactive() -> None:
        """
        Close all inactive changesets.
        """
        async with db_commit() as session:
            now = utcnow()
            stmt = (
                update(Changeset)
                .where(
                    Changeset.closed_at == null(),
                    or_(
                        Changeset.updated_at < now - CHANGESET_IDLE_TIMEOUT,
                        and_(
                            Changeset.updated_at >= now - CHANGESET_IDLE_TIMEOUT,
                            Changeset.created_at < now - CHANGESET_OPEN_TIMEOUT,
                        ),
                    ),
                )
                .values({Changeset.closed_at: now})
                .inline()
            )
            await session.execute(stmt)

    @staticmethod
    async def delete_empty() -> None:
        """
        Delete empty changesets after a timeout.
        """
        async with db_commit() as session:
            now = utcnow()
            stmt = delete(Changeset).where(
                Changeset.closed_at != null(),
                Changeset.closed_at < now - CHANGESET_EMPTY_DELETE_TIMEOUT,
                Changeset.size == 0,
            )
            await session.execute(stmt)
