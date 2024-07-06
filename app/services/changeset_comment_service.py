import logging

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment
from app.models.db.changeset_subscription import ChangesetSubscription


class ChangesetCommentService:
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
                user_id=auth_user(required=True).id,
                changeset_id=changeset_id,
                body=text,
            )
            session.add(changeset_comment)
            await session.flush()

            changeset.updated_at = changeset_comment.created_at

        await ChangesetCommentService.subscribe(changeset_id)

    @staticmethod
    async def delete_comment_unsafe(comment_id: int) -> int:
        """
        Delete any changeset comment.

        Returns the parent changeset id.
        """
        async with db_commit() as session:
            comment_stmt = select(ChangesetComment).where(ChangesetComment.id == comment_id)
            comment = await session.scalar(comment_stmt)
            if comment is None:
                raise_for().changeset_comment_not_found(comment_id)

            changeset_stmt = select(Changeset).where(Changeset.id == comment.changeset_id).with_for_update()
            changeset = await session.scalar(changeset_stmt)
            if changeset is None:
                raise_for().changeset_comment_not_found(comment_id)

            await session.delete(comment)
            changeset.updated_at = func.statement_timestamp()

            return changeset.id

    @staticmethod
    async def subscribe(changeset_id: int) -> None:
        """
        Subscribe the current user to the changeset.
        """
        user_id = auth_user(required=True).id
        logging.debug('Subscribing user %d to changeset %d', user_id, changeset_id)

        async with db_commit() as session:
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
                .inline()
            )
            await session.execute(stmt)

    @staticmethod
    async def unsubscribe(changeset_id: int) -> None:
        """
        Unsubscribe the current user from the changeset.
        """
        user_id = auth_user(required=True).id
        logging.debug('Unsubscribing user %d from changeset %d', user_id, changeset_id)

        async with db_commit() as session:
            stmt = delete(ChangesetSubscription).where(
                ChangesetSubscription.changeset_id == changeset_id,
                ChangesetSubscription.user_id == user_id,
            )
            await session.execute(stmt)
