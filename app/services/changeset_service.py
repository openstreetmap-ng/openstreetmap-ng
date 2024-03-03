from sqlalchemy import func, select

from app.db import db_autocommit
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.statement_context import apply_statement_context
from app.models.db.changeset import Changeset


class ChangesetService:
    @staticmethod
    async def create(tags: dict) -> Changeset:
        """
        Create a new changeset.
        """

        async with db_autocommit() as session:
            changeset = Changeset(
                user_id=auth_user().id,
                tags=tags,
            )

            session.add(changeset)

        return changeset

    @staticmethod
    async def update_tags(changeset_id: int, tags: dict) -> Changeset:
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

        return changeset

    @staticmethod
    async def close(changeset_id: int) -> Changeset:
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

        return changeset
