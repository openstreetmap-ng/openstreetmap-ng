import logging
from asyncio import TaskGroup
from datetime import datetime

import cython

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.translation import t, translation_context
from app.models.db.changeset_comment import (
    ChangesetComment,
    ChangesetCommentInit,
    changeset_comments_resolve_rich_text,
)
from app.models.types import ChangesetCommentId, ChangesetId, DisplayName
from app.queries.changeset_query import ChangesetQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.audit_service import audit
from app.services.email_service import EmailService
from app.services.user_subscription_service import UserSubscriptionService


class ChangesetCommentService:
    @staticmethod
    async def comment(changeset_id: ChangesetId, text: str) -> None:
        """Comment on a changeset."""
        user = auth_user(required=True)
        user_id = user['id']

        comment_init: ChangesetCommentInit = {
            'user_id': user_id,
            'changeset_id': changeset_id,
            'body': text,
        }

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT 1 FROM changeset
                WHERE id = %s
                FOR SHARE
                """,
                (changeset_id,),
            ) as r:
                if await r.fetchone() is None:
                    raise_for.changeset_not_found(changeset_id)

            async with await conn.execute(
                """
                INSERT INTO changeset_comment (
                    user_id, changeset_id, body
                )
                VALUES (
                    %(user_id)s, %(changeset_id)s, %(body)s
                )
                RETURNING id, created_at
                """,
                comment_init,
            ) as r:
                comment_id: ChangesetCommentId
                created_at: datetime
                comment_id, created_at = await r.fetchone()  # type: ignore

            await audit(
                'create_changeset_comment',
                conn,
                extra={'id': comment_id, 'changeset': changeset_id},
            )

        comment: ChangesetComment = {
            'id': comment_id,
            'user_id': user_id,
            'changeset_id': changeset_id,
            'body': text,
            'body_rich_hash': None,
            'created_at': created_at,
            'user': user,  # type: ignore
        }

        async with TaskGroup() as tg:
            tg.create_task(_send_activity_email(comment))
            tg.create_task(UserSubscriptionService.subscribe('changeset', changeset_id))

    # TODO: hide, audit
    @staticmethod
    async def delete_comment_unsafe(comment_id: ChangesetCommentId) -> ChangesetId:
        """Delete any changeset comment. Returns the parent changeset id."""
        async with (
            db(True) as conn,
            await conn.execute(
                """
                DELETE FROM changeset_comment
                WHERE id = %s
                RETURNING changeset_id
                """,
                (comment_id,),
            ) as r,
        ):
            result = await r.fetchone()
            if result is None:
                raise_for.changeset_comment_not_found(comment_id)

            changeset_id: ChangesetId = result[0]
            logging.debug(
                'Deleted changeset comment %d from changeset %d',
                comment_id,
                changeset_id,
            )
            return changeset_id


async def _send_activity_email(comment: ChangesetComment) -> None:
    changeset_id = comment['changeset_id']

    async def changeset_task():
        changeset = await ChangesetQuery.find_by_id(changeset_id)
        assert changeset is not None, f'Parent changeset {changeset_id} must exist'
        await UserQuery.resolve_users([changeset])
        return changeset

    async with TaskGroup() as tg:
        tg.create_task(changeset_comments_resolve_rich_text([comment]))
        changeset_t = tg.create_task(changeset_task())
        users = await UserSubscriptionQuery.get_subscribed_users(
            'changeset', changeset_id
        )
        if not users:
            return

    changeset = changeset_t.result()
    changeset_user_id: cython.size_t = changeset['user_id'] or 0
    changeset_comment_str = changeset.get('tags', {}).get('comment')

    comment_user = comment['user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    comment_user_id: cython.size_t = comment_user['id']
    comment_user_name = comment_user['display_name']
    ref = f'changeset-{changeset["id"]}'

    async with TaskGroup() as tg:
        for subscribed_user in users:
            subscribed_user_id: cython.size_t = subscribed_user['id']
            if subscribed_user_id == comment_user_id:
                continue

            with translation_context(subscribed_user['language']):
                is_changeset_owner: cython.bint = (
                    subscribed_user_id == changeset_user_id
                )
                subject = _get_activity_email_subject(
                    comment_user_name, is_changeset_owner
                )

            tg.create_task(
                EmailService.schedule(
                    source=None,
                    from_user_id=None,
                    to_user=subscribed_user,
                    subject=subject,
                    template_name='email/changeset-comment',
                    template_data={
                        'changeset': changeset,
                        'changeset_comment_str': changeset_comment_str,
                        'comment': comment,
                        'is_changeset_owner': is_changeset_owner,
                    },
                    ref=ref,
                )
            )


@cython.cfunc
def _get_activity_email_subject(
    comment_user_name: DisplayName,
    is_changeset_owner: cython.bint,
) -> str:
    return t(
        'user_mailer.changeset_comment_notification.commented.subject_own'
        if is_changeset_owner
        else 'user_mailer.changeset_comment_notification.commented.subject other',
        commenter=comment_user_name,
    )
