from asyncio import TaskGroup
from collections import defaultdict

import cython

from app.db import db_count, db_fetchall, db_fetchone, db_fetchrows, t_and, t_order
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
        return await db_fetchall(
            Diary,
            t"""
                SELECT * FROM diary
                WHERE id = ANY({ids})
            """,
        )

    @staticmethod
    async def count_by_user(user_id: UserId) -> int:
        """Count diaries by user id."""
        return await db_count('diary', where={'user_id': user_id})

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
        where = t_and(
            t'user_id = {user_id}' if user_id is not None else None,
            t'language = {language}' if language is not None else None,
            t'id < {before}' if before is not None else None,
            t'id > {after}' if after is not None else None,
        )
        order = t_order('desc' if order_desc else 'asc')

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

        return await db_fetchall(Diary, query)

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
        return await db_count('diary_comment', where={'user_id': user_id})

    @staticmethod
    async def find_by_id(comment_id: DiaryCommentId) -> DiaryComment | None:
        """Find a diary comment by id."""
        return await db_fetchone(
            DiaryComment,
            t"""
                SELECT * FROM diary_comment
                WHERE id = {comment_id}
            """,
        )

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
        where = t_and(
            t'user_id = {user_id}',
            t'id < {before}' if before is not None else None,
            t'id > {after}' if after is not None else None,
        )
        order = t_order('desc' if order_desc else 'asc')

        query = t"""
            SELECT * FROM diary_comment
            WHERE {where:q}
            ORDER BY id {order:q}
            LIMIT {limit}
        """

        # Always return in descending order
        if not order_desc:
            query = t"""
                SELECT * FROM ({query:q})
                ORDER BY id DESC
            """

        return await db_fetchall(DiaryComment, query)

    @staticmethod
    async def resolve_num_comments(diaries: list[Diary]) -> None:
        """Resolve the number of comments for each diary."""
        if not diaries:
            return

        id_map = {diary['id']: diary for diary in diaries}
        ids = list(id_map)

        rows = await db_fetchrows(t"""
            SELECT c.value, (
                SELECT COUNT(*) FROM diary_comment
                WHERE diary_id = c.value
            ) FROM unnest({ids}) AS c(value)
        """)
        for diary_id, count in rows:
            id_map[diary_id]['num_comments'] = count
