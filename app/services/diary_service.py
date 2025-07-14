import logging
from typing import Any

from psycopg.sql import SQL, Composable
from shapely import Point

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.models.db.diary import DiaryInit
from app.models.types import DiaryId, LocaleCode, UserId
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
        """
        Post a new diary entry.

        Returns the diary id.
        """
        user_id = auth_user(required=True)['id']

        diary_init: DiaryInit = {
            'user_id': user_id,
            'title': title,
            'body': body,
            'language': language,
            'point': point,
        }

        async with (
            db(True) as conn,
            await conn.execute(
                """
                INSERT INTO diary (
                    user_id, title, body, language, point
                )
                VALUES (
                    %(user_id)s, %(title)s, %(body)s, %(language)s, ST_QuantizeCoordinates(%(point)s, 5)
                )
                RETURNING id
                """,
                diary_init,
            ) as r,
        ):
            diary_id: DiaryId = (await r.fetchone())[0]  # type: ignore

        logging.debug('Created diary %d by user %d', diary_id, user_id)
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
    ) -> None:
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

    @staticmethod
    async def delete(
        diary_id: DiaryId, *, current_user_id: UserId | None = None
    ) -> None:
        """Delete a diary entry."""
        conditions: list[Composable] = [SQL('id = %s')]
        params: list[Any] = [diary_id]

        if current_user_id is not None:
            conditions.append(SQL('user_id = %s'))
            params.append(current_user_id)

        query = SQL("""
            DELETE FROM diary
            WHERE {conditions}
        """).format(conditions=SQL(' AND ').join(conditions))

        async with db(True) as conn:
            await conn.execute(query, params)
