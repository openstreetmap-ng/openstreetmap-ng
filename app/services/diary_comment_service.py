from asyncio import TaskGroup
from datetime import datetime
from typing import Any

from psycopg.sql import SQL, Composable
from zid import zid

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.translation import t, translation_context
from app.models.db.diary_comment import (
    DiaryComment,
    DiaryCommentInit,
    diary_comments_resolve_rich_text,
)
from app.models.types import DiaryCommentId, DiaryId, UserId
from app.queries.diary_query import DiaryQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.audit_service import audit
from app.services.email_service import EmailService
from app.services.user_subscription_service import UserSubscriptionService


class DiaryCommentService:
    @staticmethod
    async def comment(diary_id: DiaryId, body: str):
        """Create a new diary comment."""
        user = auth_user(required=True)
        user_id = user['id']

        comment_id: DiaryCommentId = zid()  # type: ignore
        comment_init: DiaryCommentInit = {
            'id': comment_id,
            'user_id': user_id,
            'diary_id': diary_id,
            'body': body,
        }

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT id FROM diary
                WHERE id = %s
                FOR SHARE
                """,
                (diary_id,),
            ) as r:
                result = await r.fetchone()
                if result is None:
                    raise_for.diary_not_found(diary_id)

            async with await conn.execute(
                """
                INSERT INTO diary_comment (
                    id, user_id, diary_id, body
                )
                VALUES (
                    %(id)s, %(user_id)s, %(diary_id)s, %(body)s
                )
                RETURNING created_at
                """,
                comment_init,
            ) as r:
                created_at: datetime = (await r.fetchone())[0]  # type: ignore

            await audit(
                'create_diary_comment',
                conn,
                extra={'id': comment_id, 'diary': diary_id},
            )

        comment: DiaryComment = {
            'id': comment_id,
            'user_id': user_id,
            'diary_id': diary_id,
            'body': body,
            'body_rich_hash': None,
            'created_at': created_at,
            'user': user,  # type: ignore
        }

        async with TaskGroup() as tg:
            tg.create_task(_send_activity_email(comment))
            tg.create_task(UserSubscriptionService.subscribe('diary', diary_id))

    # TODO: hide, audit
    @staticmethod
    async def delete(comment_id: DiaryCommentId, *, current_user_id: UserId | None):
        """Delete a diary comment."""
        conditions: list[Composable] = [SQL('id = %s')]
        params: list[Any] = [comment_id]

        if current_user_id is not None:
            conditions.append(SQL('user_id = %s'))
            params.append(current_user_id)

        query = SQL("""
            DELETE FROM diary_comment
            WHERE {conditions}
        """).format(conditions=SQL(' AND ').join(conditions))

        async with db(True) as conn:
            await conn.execute(query, params)


async def _send_activity_email(comment: DiaryComment):
    diary_id = comment['diary_id']

    async with TaskGroup() as tg:
        tg.create_task(diary_comments_resolve_rich_text([comment]))
        diary_t = tg.create_task(DiaryQuery.find_by_id(diary_id))
        users = await UserSubscriptionQuery.get_subscribed_users('diary', diary_id)
        if not users:
            return

    diary = diary_t.result()
    assert diary is not None, f'Parent diary {diary_id} must exist'

    comment_user = comment['user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    comment_user_id = comment_user['id']
    comment_user_name = comment_user['display_name']
    ref = f'diary-{diary_id}'

    async with TaskGroup() as tg:
        for subscribed_user in users:
            subscribed_user_id = subscribed_user['id']
            if subscribed_user_id == comment_user_id:
                continue

            with translation_context(subscribed_user['language']):
                subject = t(
                    'user_mailer.diary_comment_notification.subject',
                    user=comment_user_name,
                )

            tg.create_task(
                EmailService.schedule(
                    source='diary_comment',
                    from_user_id=comment_user_id,
                    to_user=subscribed_user,
                    subject=subject,
                    template_name='email/diary-comment',
                    template_data={'diary': diary, 'comment': comment},
                    ref=ref,
                )
            )
