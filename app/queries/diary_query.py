from asyncio import TaskGroup
from collections import defaultdict
from string.templatelib import Template
from typing import Any

import cython
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.db import db
from app.lib.http.client import HTTPError
from app.models.db.diary import Diary
from app.models.db.diary_comment import DiaryComment
from app.models.types import DiaryCommentId, DiaryId, LocaleCode, UserId
from app.queries.nominatim_query import NominatimQuery


class DiaryQuery:
    @staticmethod
    async def find_by_id(diary_id: DiaryId) -> Diary | None:
        """Find a diary by id."""
        diaries = await DiaryQuery.find_by_ids([diary_id])
        return next(iter(diaries), None)

    @staticmethod
    async def find_by_ids(ids: list[DiaryId]) -> list[Diary]:
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM diary
                WHERE id = ANY(%s)
                """,
                (ids,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def count_by_user(user_id: UserId) -> int:
        """Count diaries by user id."""
        async with (
            db() as conn,
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
    async def find_recent(
        *,
        user_id: UserId | None = None,
        language: LocaleCode | None = None,
        after: DiaryId | None = None,
        before: DiaryId | None = None,
        limit: int,
    ) -> list[Diary]:
        """Find recent diaries."""
        assert user_id is None or language is None, (
            'Only one of user_id and language can be set'
        )

        order_desc: cython.bint = (after is None) or (before is not None)
        filters: list[Template] = []

        if user_id is not None:
            filters.append(t'user_id = {user_id}')
        if language is not None:
            filters.append(t'language = {language}')
        if before is not None:
            filters.append(t'id < {before}')
        if after is not None:
            filters.append(t'id > {after}')

        where = SQL(' AND ').join(filters) if filters else SQL('TRUE')
        order = SQL('DESC') if order_desc else SQL('ASC')

        query = t"""
            SELECT * FROM diary
            WHERE {where:q}
            ORDER BY id {order:q}
            LIMIT {limit}
        """

        # Always return in consistent order regardless of the query
        if not order_desc:
            query = t"""
                SELECT * FROM ({query:q})
                ORDER BY id DESC
            """

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def resolve_location_name(diaries: list[Diary]) -> None:
        """Resolve location name fields for diaries."""

        async def task(diary: Diary):
            try:
                result = await NominatimQuery.reverse(diary['point'])  # pyright: ignore [reportArgumentType]
            except HTTPError:
                return
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

        id_map = defaultdict[DiaryId, list[DiaryComment]](list)
        for comment in comments:
            id_map[comment['diary_id']].append(comment)

        diaries = await DiaryQuery.find_by_ids(list(id_map))
        for diary in diaries:
            for comment in id_map[diary['id']]:
                comment['diary'] = diary


# === Diary Comments ===


class DiaryCommentQuery:
    @staticmethod
    async def count_by_user(user_id: UserId) -> int:
        """Count diary comments by user id (for profile stats)."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT COUNT(*)
                FROM diary_comment
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def find_by_id(comment_id: DiaryCommentId) -> DiaryComment | None:
        """Find a diary comment by id."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM diary_comment
                WHERE id = %s
                """,
                (comment_id,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def find_by_user(
        user_id: UserId,
        *,
        before: DiaryCommentId | None = None,
        after: DiaryCommentId | None = None,
        limit: int,
    ) -> list[DiaryComment]:
        """Find comments by user id."""
        order_desc: cython.bint = (after is None) or (before is not None)
        conditions: list[Composable] = [SQL('user_id = %s')]
        params: list[Any] = [user_id]

        if before is not None:
            conditions.append(SQL('id < %s'))
            params.append(before)

        if after is not None:
            conditions.append(SQL('id > %s'))
            params.append(after)

        query = SQL("""
            SELECT * FROM diary_comment
            WHERE {where}
            ORDER BY id {order}
            LIMIT %s
        """).format(
            where=SQL(' AND ').join(conditions or (SQL('TRUE'),)),
            order=SQL('DESC' if order_desc else 'ASC'),
        )
        params.append(limit)

        # Always return in descending order
        if not order_desc:
            query = SQL("""
                SELECT * FROM ({})
                ORDER BY id DESC
            """).format(query)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def resolve_num_comments(diaries: list[Diary]) -> None:
        """Resolve the number of comments for each diary."""
        if not diaries:
            return

        id_map = {diary['id']: diary for diary in diaries}

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT c.value, (
                    SELECT COUNT(*) FROM diary_comment
                    WHERE diary_id = c.value
                ) FROM unnest(%s) AS c(value)
                """,
                (list(id_map),),
            ) as r,
        ):
            for diary_id, count in await r.fetchall():
                id_map[diary_id]['num_comments'] = count
