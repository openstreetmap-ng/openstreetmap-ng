import logging
from asyncio import TaskGroup

import cython
from sqlalchemy import delete

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.translation import t, translation_context
from app.models.db.diary_comment import DiaryComment
from app.models.db.mail import MailSource
from app.models.db.user_subscription import UserSubscriptionTarget
from app.queries.diary_query import DiaryQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.email_service import EmailService
from app.services.user_subscription_service import UserSubscriptionService


class DiaryCommentService:
    @staticmethod
    async def comment(diary_id: int, body: str) -> None:
        """
        Create a new diary comment.
        """
        user = auth_user(required=True)
        async with db_commit() as session:
            comment = DiaryComment(
                user_id=user.id,
                diary_id=diary_id,
                body=body,
            )
            session.add(comment)
        logging.debug('Created diary comment on diary %d by user %d', diary_id, user.id)
        comment.user = user
        async with TaskGroup() as tg:
            tg.create_task(_send_activity_email(comment))
            tg.create_task(UserSubscriptionService.subscribe(UserSubscriptionTarget.diary, diary_id))

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


async def _send_activity_email(comment: DiaryComment) -> None:
    async with TaskGroup() as tg:
        tg.create_task(comment.resolve_rich_text())
        diary_t = tg.create_task(DiaryQuery.find_one_by_id(comment.diary_id))
        users = await UserSubscriptionQuery.get_subscribed_users(UserSubscriptionTarget.diary, comment.diary_id)
        if not users:
            return

    diary = diary_t.result()
    if diary is None:
        raise AssertionError('Parent diary must exist')
    comment_user = comment.user
    comment_user_id: cython.longlong = comment_user.id
    comment_user_name = comment_user.display_name
    async with TaskGroup() as tg:
        for subscribed_user in users:
            subscribed_user_id: cython.longlong = subscribed_user.id
            if subscribed_user_id == comment_user_id:
                continue
            with translation_context(subscribed_user.language):
                subject = t('user_mailer.diary_comment_notification.subject', user=comment_user_name)
            tg.create_task(
                EmailService.schedule(
                    source=MailSource.diary_comment,
                    from_user=comment_user,
                    to_user=subscribed_user,
                    subject=subject,
                    template_name='email/diary_comment.jinja2',
                    template_data={'diary': diary, 'comment': comment},
                    ref=f'diary-{diary.id}',
                )
            )
