import logging

from sqlalchemy import delete

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.models.db.diary_comment import DiaryComment
from app.models.db.user_subscription import UserSubscriptionTarget
from app.services.user_subscription_service import UserSubscriptionService


class DiaryCommentService:
    @staticmethod
    async def comment(diary_id: int, body: str) -> None:
        """
        Create a new diary comment.
        """
        user_id = auth_user(required=True).id
        async with db_commit() as session:
            session.add(
                DiaryComment(
                    user_id=user_id,
                    diary_id=diary_id,
                    body=body,
                )
            )
        logging.debug('Created diary comment on diary %d by user %d', diary_id, user_id)
        await UserSubscriptionService.subscribe(UserSubscriptionTarget.diary, diary_id)

    @staticmethod
    async def delete(comment_id: int, *, current_user_id: int | None) -> None:
        """
        Delete a diary comment.
        """
        async with db_commit() as session:
            stmt = delete(DiaryComment)
            where_and = [DiaryComment.id == comment_id]
            if current_user_id is not None:
                where_and.append(DiaryComment.user_id == current_user_id)
            await session.execute(stmt.where(*where_and))
