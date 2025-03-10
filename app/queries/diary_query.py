from asyncio import TaskGroup
from collections import defaultdict
from typing import Any

import cython
from httpx import HTTPError
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.db import db2
from app.models.db.diary import Diary, DiaryId
from app.models.db.diary_comment import DiaryComment
from app.models.db.user import UserId
from app.models.types import LocaleCode
from app.queries.nominatim_query import NominatimQuery


class DiaryQuery:
    @staticmethod
    async def find_one_by_id(diary_id: DiaryId) -> Diary | None:
        """Find a diary by id."""
        diaries = await DiaryQuery.find_many_by_ids([diary_id])
        return next(iter(diaries), None)

    @staticmethod
    async def find_many_by_ids(ids: list[DiaryId]) -> list[Diary]:
        async with (
            db2() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM diary
                WHERE id IN %s
                """,
                (ids,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def count_by_user_id(user_id: UserId) -> int:
        """Count diaries by user id."""
        async with (
            db2() as conn,
            await conn.execute(
                """
                SELECT COUNT(*) FROM diary
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def find_many_recent(
        *,
        user_id: UserId | None = None,
        language: LocaleCode | None = None,
        after: DiaryId | None = None,
        before: DiaryId | None = None,
        limit: int,
    ) -> list[Diary]:
        """Find recent diaries."""
        assert user_id is None or language is None, 'Only one of user_id and language can be set'

        order_desc: cython.bint = (after is None) or (before is not None)
        conditions: list[Composable] = []
        params: list[Any] = []

        if user_id is not None:
            conditions.append(SQL('user_id = %s'))
            params.append(user_id)

        if language is not None:
            conditions.append(SQL('language = %s'))
            params.append(language)

        if before is not None:
            conditions.append(SQL('id < %s'))
            params.append(before)

        if after is not None:
            conditions.append(SQL('id > %s'))
            params.append(after)

        query = SQL("""
            SELECT * FROM diary
            WHERE {where}
            ORDER BY id {order}
            LIMIT %s
        """).format(
            where=SQL(' AND ').join(conditions) if conditions else SQL('TRUE'),
            order=SQL('DESC' if order_desc else 'ASC'),
        )
        params.append(limit)

        # Always return in consistent order regardless of the query
        if not order_desc:
            query = SQL("""
                SELECT * FROM ({})
                ORDER BY id DESC
            """).format(query)

        async with db2() as conn, await conn.cursor(row_factory=dict_row).execute(query, params) as r:
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def resolve_location_name(diaries: list[Diary]) -> None:
        """Resolve location name fields for diaries."""

        async def task(diary: Diary) -> None:
            try:
                result = await NominatimQuery.reverse(diary['point'])  # pyright: ignore [reportArgumentType]
            except HTTPError:
                pass
            else:
                if result is not None:
                    diary['location_name'] = result.display_name

        async with TaskGroup() as tg:
            for d in diaries:
                if d['point'] is not None:
                    tg.create_task(task(d))

    @staticmethod
    async def resolve_diary(comments: list[DiaryComment]) -> None:
        """Resolve diary fields for the given comments."""
        if not comments:
            return

        id_map: dict[DiaryId, list[DiaryComment]] = defaultdict(list)
        for comment in comments:
            id_map[comment['diary_id']].append(comment)

        diaries = await DiaryQuery.find_many_by_ids(list(id_map))
        for diary in diaries:
            for comment in id_map[diary['id']]:
                comment['diary'] = diary
