import logging

from sqlalchemy import func, select

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment
from app.models.db.user_subscription import UserSubscriptionTarget
from app.services.user_subscription_service import UserSubscriptionService


class ChangesetCommentService:
    @staticmethod
    async def comment(changeset_id: int, text: str) -> None:
        """
        Comment on a changeset.
        """
        user_id = auth_user(required=True).id
        async with db_commit() as session:
            stmt = select(Changeset).where(Changeset.id == changeset_id).with_for_update()
            changeset = await session.scalar(stmt)
            if changeset is None:
                raise_for().changeset_not_found(changeset_id)
            changeset_comment = ChangesetComment(
                user_id=user_id,
                changeset_id=changeset_id,
                body=text,
            )
            session.add(changeset_comment)
            await session.flush()
            changeset.updated_at = changeset_comment.created_at
        logging.debug('Created changeset comment on changeset %d by user %d', changeset_id, user_id)
        await UserSubscriptionService.subscribe(UserSubscriptionTarget.changeset, changeset_id)

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

            changeset_id = comment.changeset_id
            changeset_stmt = select(Changeset).where(Changeset.id == changeset_id).with_for_update()
            changeset = await session.scalar(changeset_stmt)
            if changeset is None:
                raise_for().changeset_comment_not_found(comment_id)

            await session.delete(comment)
            changeset.updated_at = func.statement_timestamp()

        logging.debug('Deleted changeset comment %d from changeset %d', comment_id, changeset_id)
        return changeset_id
