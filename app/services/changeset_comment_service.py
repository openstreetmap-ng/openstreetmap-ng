from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.db import db_autocommit
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
            async with db_autocommit() as session:
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

        async with db_autocommit() as session:
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
        # TODO: update changeset timestamp

        async with db_autocommit() as session:
            stmt = select(Changeset.closed_at).where(Changeset.id == changeset_id).with_for_update()
            rows = (await session.execute(stmt)).all()

            if not rows:
                raise_for().changeset_not_found(changeset_id)
            if rows[0][0] is not None:
                raise_for().changeset_not_closed(changeset_id)

            session.add(
                ChangesetComment(
                    user_id=auth_user().id,
                    changeset_id=changeset_id,
                    body=text,
                )
            )

    @staticmethod
    async def delete_comment_unsafe(comment_id: int) -> None:
        """
        Delete any changeset comment.
        """

        async with db_autocommit() as session:
            stmt = delete(ChangesetComment).where(ChangesetComment.id == comment_id)

            if (await session.execute(stmt)).rowcount != 1:
                raise_for().changeset_comment_not_found(comment_id)
