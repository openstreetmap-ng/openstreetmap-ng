import logging
from asyncio import TaskGroup

import cython
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.options_context import options_context
from app.lib.translation import t, translation_context
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment
from app.models.db.mail import MailSource
from app.models.db.user import User
from app.models.db.user_subscription import UserSubscriptionTarget
from app.models.types import DisplayNameType
from app.queries.changeset_query import ChangesetQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.email_service import EmailService
from app.services.user_subscription_service import UserSubscriptionService


class ChangesetCommentService:
    @staticmethod
    async def comment(changeset_id: int, text: str) -> None:
        """
        Comment on a changeset.
        """
        user = auth_user(required=True)
        async with db_commit() as session:
            stmt = select(Changeset).where(Changeset.id == changeset_id).with_for_update()
            changeset = await session.scalar(stmt)
            if changeset is None:
                raise_for.changeset_not_found(changeset_id)
            changeset_comment = ChangesetComment(
                user_id=user.id,
                changeset_id=changeset_id,
                body=text,
            )
            session.add(changeset_comment)
            await session.flush()
            changeset.updated_at = changeset_comment.created_at

        logging.debug('Created changeset comment on changeset %d by user %d', changeset_id, user.id)
        changeset_comment.user = user
        async with TaskGroup() as tg:
            tg.create_task(_send_activity_email(changeset_comment))
            tg.create_task(UserSubscriptionService.subscribe(UserSubscriptionTarget.changeset, changeset_id))

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
                raise_for.changeset_comment_not_found(comment_id)

            changeset_id = comment.changeset_id
            changeset_stmt = select(Changeset).where(Changeset.id == changeset_id).with_for_update()
            changeset = await session.scalar(changeset_stmt)
            if changeset is None:
                raise_for.changeset_comment_not_found(comment_id)

            await session.delete(comment)
            changeset.updated_at = func.statement_timestamp()

        logging.debug('Deleted changeset comment %d from changeset %d', comment_id, changeset_id)
        return changeset_id


async def _send_activity_email(comment: ChangesetComment) -> None:
    async def changeset_task() -> Changeset:
        with options_context(joinedload(Changeset.user).load_only(User.display_name)):
            changeset = await ChangesetQuery.find_by_id(comment.changeset_id)
            if changeset is None:
                raise AssertionError('Parent changeset must exist')
            return changeset

    async with TaskGroup() as tg:
        tg.create_task(comment.resolve_rich_text())
        changeset_t = tg.create_task(changeset_task())
        users = await UserSubscriptionQuery.get_subscribed_users(UserSubscriptionTarget.changeset, comment.changeset_id)
        if not users:
            return

    changeset = changeset_t.result()
    changeset_user_id: cython.longlong = changeset.user_id or 0
    changeset_comment_str = changeset.tags.get('comment')
    comment_user = comment.user
    comment_user_id: cython.longlong = comment_user.id
    comment_user_name = comment_user.display_name
    async with TaskGroup() as tg:
        for subscribed_user in users:
            subscribed_user_id: cython.longlong = subscribed_user.id
            if subscribed_user_id == comment_user_id:
                continue
            is_changeset_owner: cython.char = subscribed_user_id == changeset_user_id
            with translation_context(subscribed_user.language):
                subject = _get_activity_email_subject(comment_user_name, is_changeset_owner)
            tg.create_task(
                EmailService.schedule(
                    source=MailSource.system,
                    from_user=None,
                    to_user=subscribed_user,
                    subject=subject,
                    template_name='email/changeset_comment.jinja2',
                    template_data={
                        'changeset': changeset,
                        'changeset_comment_str': changeset_comment_str,
                        'comment': comment,
                        'is_changeset_owner': is_changeset_owner,
                    },
                    ref=f'changeset-{changeset.id}',
                )
            )


@cython.cfunc
def _get_activity_email_subject(
    comment_user_name: DisplayNameType,
    is_changeset_owner: cython.char,
) -> str:
    if is_changeset_owner:
        return t('user_mailer.changeset_comment_notification.commented.subject_own', commenter=comment_user_name)
    else:
        return t('user_mailer.changeset_comment_notification.commented.subject other', commenter=comment_user_name)
