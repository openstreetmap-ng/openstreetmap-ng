from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment
from app.models.db.changeset_subscription import ChangesetSubscription


class ChangesetCommentService:
    @staticmethod
    async def subscribe(changeset_id: int) -> None:
        """
        Subscribe current user to changeset discussion.
        """
        try:
            async with db_commit() as session:
                session.add(
                    ChangesetSubscription(
                        user_id=auth_user().id,
                        changeset_id=changeset_id,
                    )
                )

        except IntegrityError:
            # TODO: raise_for().changeset_not_found(changeset_id)
            raise_for().changeset_already_subscribed(changeset_id)

    @staticmethod
    async def unsubscribe(changeset_id: int) -> None:
        """
        Unsubscribe current user from changeset discussion.
        """
        async with db_commit() as session:
            stmt = delete(ChangesetSubscription).where(
                ChangesetSubscription.user_id == auth_user().id,
                ChangesetSubscription.changeset_id == changeset_id,
            )

            if (await session.execute(stmt)).rowcount != 1:
                raise_for().changeset_not_subscribed(changeset_id)

    @staticmethod
    async def comment(changeset_id: int, text: str) -> None:
        """
        Comment on a changeset.
        """
        async with db_commit() as session:
            stmt = select(Changeset).where(Changeset.id == changeset_id).with_for_update()
            changeset = await session.scalar(stmt)
            if changeset is None:
                raise_for().changeset_not_found(changeset_id)

            changeset_comment = ChangesetComment(
                user_id=auth_user().id,
                changeset_id=changeset_id,
                body=text,
            )
            session.add(changeset_comment)
            await session.flush()

            changeset.updated_at = changeset_comment.created_at

    @staticmethod
    async def delete_comment_unsafe(comment_id: int) -> int:
        """
        Delete any changeset comment.

        Returns the parent changeset id.
        """
        async with db_commit() as session:
            stmt = select(ChangesetComment).where(ChangesetComment.id == comment_id)
            comment = await session.scalar(stmt)
            if comment is None:
                raise_for().changeset_comment_not_found(comment_id)

            stmt = select(Changeset).where(Changeset.id == comment.changeset_id).with_for_update()
            changeset = await session.scalar(stmt)
            if changeset is None:
                raise_for().changeset_comment_not_found(comment_id)

            await session.delete(comment)
            changeset.updated_at = func.statement_timestamp()

            return changeset.id
