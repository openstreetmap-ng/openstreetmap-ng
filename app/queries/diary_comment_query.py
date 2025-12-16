from typing import Any

import cython
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.db import db
from app.models.db.diary import Diary
from app.models.db.diary_comment import DiaryComment
from app.models.types import DiaryCommentId, UserId


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
            where=SQL(' AND ').join(conditions) if conditions else SQL('TRUE'),
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
