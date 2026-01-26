from typing import Any

from psycopg.sql import SQL, Composable
from shapely import Point

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.models.db.diary import DiaryInit
from app.models.types import DiaryId, ImageProxyId, LocaleCode, UserId
from app.services.audit_service import audit
from app.services.user_subscription_service import UserSubscriptionService


class DiaryService:
    @staticmethod
    async def create(
        *,
        title: str,
        body: str,
        language: LocaleCode,
        point: Point | None,
    ) -> DiaryId:
        """Post a new diary entry."""
        user_id = auth_user(required=True)['id']

        diary_init: DiaryInit = {
            'user_id': user_id,
            'title': title,
            'body': body,
            'language': language,
            'point': point,
        }

        async with db(True) as conn:
            async with await conn.execute(
                """
                INSERT INTO diary (
                    user_id, title, body, language, point
                )
                VALUES (
                    %(user_id)s, %(title)s, %(body)s, %(language)s, ST_QuantizeCoordinates(%(point)s, 7)
                )
                RETURNING id
                """,
                diary_init,
            ) as r:
                diary_id: DiaryId = (await r.fetchone())[0]  # type: ignore

            await audit('create_diary', conn, extra={'id': diary_id, 'title': title})

        await UserSubscriptionService.subscribe('diary', diary_id)
        return diary_id

    @staticmethod
    async def update(
        *,
        diary_id: DiaryId,
        title: str,
        body: str,
        language: LocaleCode,
        point: Point | None,
    ):
        """Update a diary entry."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            result = await conn.execute(
                """
                UPDATE diary
                SET
                    title = %(title)s,
                    body = %(body)s,
                    body_rich_hash = CASE
                        WHEN %(body)s != diary.body THEN NULL
                        ELSE body_rich_hash
                    END,
                    language = %(language)s,
                    point = %(point)s,
                    updated_at = DEFAULT
                WHERE id = %(diary_id)s
                AND user_id = %(user_id)s
                """,
                {
                    'diary_id': diary_id,
                    'user_id': user_id,
                    'title': title,
                    'body': body,
                    'language': language,
                    'point': point,
                },
            )

            if not result.rowcount:
                raise_for.diary_not_found(diary_id)

            await audit('update_diary', conn, extra={'id': diary_id})

    @staticmethod
    async def delete(diary_id: DiaryId, *, current_user_id: UserId | None = None):
        """Delete a diary entry."""
        conditions: list[Composable] = [SQL('id = %s')]
        params: list[Any] = [diary_id]

        if current_user_id is not None:
            conditions.append(SQL('user_id = %s'))
            params.append(current_user_id)

        query = SQL("""
            DELETE FROM diary
            WHERE {conditions}
            RETURNING body_image_proxy_ids
        """).format(conditions=SQL(' AND ').join(conditions))

        removed: list[ImageProxyId] = []

        async with db(True) as conn:
            async with await conn.execute(query, params) as r:
                rows: list[tuple[list[ImageProxyId] | None]] = await r.fetchall()

            if rows:
                for row in rows:
                    if ids := row[0]:
                        removed.extend(ids)

                await audit('delete_diary', conn, extra={'id': diary_id})

        # TODO: Re-enable image proxy pruning via background service (cache issue)
        # if removed:
        #     await ImageProxyService.prune_unused(removed)
