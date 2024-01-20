from sqlalchemy import func

from app.db import DB
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.joinedload_context import get_joinedload
from app.models.db.changeset import Changeset


class ChangesetService:
    @staticmethod
    async def create(tags: dict) -> Changeset:
        """
        Create a new changeset.
        """

        async with DB() as session:
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

        async with DB() as session, session.begin():
            changeset = await session.get(
                Changeset,
                changeset_id,
                options=[get_joinedload()],
                with_for_update=True,
            )

            if not changeset:
                raise_for().changeset_not_found(changeset_id)
            if changeset.user_id != auth_user().id:
                raise_for().changeset_access_denied()
            if changeset.closed_at:
                raise_for().changeset_already_closed(changeset_id, changeset.closed_at)

            changeset.tags = tags

        return changeset

    @staticmethod
    async def close(changeset_id: int) -> Changeset:
        """
        Close a changeset.
        """

        async with DB() as session, session.begin():
            changeset = await session.get(
                Changeset,
                changeset_id,
                options=[get_joinedload()],
                with_for_update=True,
            )

            if not changeset:
                raise_for().changeset_not_found(changeset_id)
            if changeset.user_id != auth_user().id:
                raise_for().changeset_access_denied()
            if changeset.closed_at:
                raise_for().changeset_already_closed(changeset_id, changeset.closed_at)

            changeset.closed_at = func.now()

        return changeset
