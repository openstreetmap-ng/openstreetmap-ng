from typing import Any

import cython
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.db import db2
from app.lib.standard_pagination import standard_pagination_range
from app.limits import DIARY_COMMENTS_PAGE_SIZE
from app.models.db.diary import Diary, DiaryId
from app.models.db.diary_comment import DiaryComment, DiaryCommentId
from app.models.db.user import UserId


class DiaryCommentQuery:
    @staticmethod
    async def count_by_user_id(user_id: UserId) -> int:
        """Count diary comments by user id."""
        async with (
            db2() as conn,
            await conn.execute(
                """
                SELECT COUNT(*)
                FROM diary_comment
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            row = await r.fetchone()
            return row[0] if row is not None else 0

    @staticmethod
    async def find_one_by_id(comment_id: DiaryCommentId) -> DiaryComment | None:
        """Find a diary comment by id."""
        async with (
            db2() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT *
                FROM diary_comment
                WHERE id = %s
                """,
                (comment_id,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def find_many_by_user_id(
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
            SELECT *
            FROM diary_comment
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
            db2() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def get_diary_page(
        diary_id: DiaryId,
        *,
        page: int,
        num_items: int,
    ) -> list[DiaryComment]:
        """Get comments for the given diary page."""
        stmt_limit, stmt_offset = standard_pagination_range(
            page,
            page_size=DIARY_COMMENTS_PAGE_SIZE,
            num_items=num_items,
        )

        async with (
            db2() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM (
                    SELECT *
                    FROM diary_comment
                    WHERE diary_id = %s
                    ORDER BY id DESC
                    OFFSET %s
                    LIMIT %s
                ) AS subquery
                ORDER BY id ASC
                """,
                (diary_id, stmt_offset, stmt_limit),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def resolve_num_comments(diaries: list[Diary]) -> None:
        """Resolve the number of comments for each diary."""
        if not diaries:
            return

        id_map = {diary['id']: diary for diary in diaries}

        async with (
            db2() as conn,
            await conn.execute(
                """
                SELECT diary_id, COUNT(*)
                FROM diary_comment
                WHERE diary_id = ANY(%s)
                GROUP BY diary_id
                """,
                (list(id_map),),
            ) as r,
        ):
            rows = await r.fetchall()

            for diary_id, count in rows:
                id_map[diary_id]['num_comments'] = count

            # Set zero for diaries without comments
            if len(rows) < len(id_map):
                for diary in id_map.values():
                    diary.setdefault('num_comments', 0)
