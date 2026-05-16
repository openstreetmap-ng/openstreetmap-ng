from datetime import date, datetime
from typing import Literal

from psycopg import AsyncConnection, IsolationLevel
from psycopg.abc import Params, Query
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable
from psycopg.sql import Literal as PgLiteral
from shapely import MultiPolygon
from shapely.geometry.base import BaseGeometry

from app.db import db
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import (
    ChangesetComment,
    changeset_comments_resolve_rich_text,
)
from app.models.types import ChangesetId, UserId
from app.queries.timescaledb_query import TimescaleDBQuery


class ChangesetQuery:
    @staticmethod
    async def find_by_ids(changeset_ids: list[ChangesetId]) -> list[Changeset]:
        """Find changesets by ids."""
        if not changeset_ids:
            return []

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM changeset
                WHERE id = ANY(%s)
                """,
                (changeset_ids,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def count_by_user(user_id: UserId) -> int:
        """Count changesets by user id."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT COUNT(*) FROM changeset
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def find_adjacent_ids(
        changeset_id: ChangesetId, *, user_id: UserId
    ) -> tuple[ChangesetId | None, ChangesetId | None]:
        """Find the user's previous and next changeset ids."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT
                (   SELECT MAX(id) FROM changeset
                    WHERE id < %(changeset_id)s AND user_id = %(user_id)s),
                (   SELECT MIN(id) FROM changeset
                    WHERE id > %(changeset_id)s AND user_id = %(user_id)s)
                """,
                {'changeset_id': changeset_id, 'user_id': user_id},
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def find_by_id(
        changeset_id: ChangesetId,
        *,
        conn: AsyncConnection | None = None,
    ) -> Changeset | None:
        """Find a changeset by id."""
        async with (
            db(conn) as conn,
            await conn.cursor(row_factory=dict_row).execute(
                SQL("""
                    SELECT * FROM changeset
                    WHERE id = %s
                    {}
                """).format(SQL('FOR UPDATE' if not conn.read_only else '')),
                (changeset_id,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def find(
        *,
        changeset_ids: list[ChangesetId] | None = None,
        changeset_id_before: ChangesetId | None = None,
        user_ids: list[UserId] | None = None,
        created_before: datetime | None = None,
        created_after: datetime | None = None,
        closed_after: datetime | None = None,
        is_open: bool | None = None,
        geometry: BaseGeometry | None = None,
        legacy_geometry: bool = False,
        sort: Literal['asc', 'desc'] = 'asc',
        limit: int | None,
    ) -> list[Changeset]:
        """Find changesets by query."""
        conditions: list[Composable] = []
        params = {}

        if changeset_ids is not None:
            conditions.append(SQL('id = ANY(%(changeset_ids)s)'))
            params['changeset_ids'] = changeset_ids

        if changeset_id_before is not None:
            conditions.append(SQL('id < %(changeset_id_before)s'))
            params['changeset_id_before'] = changeset_id_before

        if user_ids is not None:
            if not user_ids:
                return []

            conditions.append(SQL('user_id = ANY(%(user_ids)s)'))
            params['user_ids'] = user_ids

        if created_before is not None:
            conditions.append(SQL('created_at < %(created_before)s'))
            params['created_before'] = created_before

        if created_after is not None:
            conditions.append(SQL('created_at > %(created_after)s'))
            params['created_after'] = created_after

        if closed_after is not None:
            conditions.append(
                SQL('closed_at IS NOT NULL AND closed_at >= %(closed_after)s')
            )
            params['closed_after'] = closed_after

        conditions.append(
            SQL('(%(is_open)s::bool IS NULL OR (closed_at IS NULL) = %(is_open)s)')
        )
        params['is_open'] = is_open

        if geometry is not None:
            conditions.append(
                SQL(
                    'union_bounds && %(geometry)s'
                    if legacy_geometry
                    else """
                    EXISTS (
                        SELECT 1 FROM changeset_bounds
                        WHERE changeset_id = changeset.id
                        AND bounds && %(geometry)s
                    )
                    """
                )
            )
            params['geometry'] = geometry

        where_clause = SQL(' AND ').join(conditions or (SQL('TRUE'),))
        order_clause = SQL(sort)

        if limit is not None:
            limit_clause = SQL('LIMIT %(limit)s')
            params['limit'] = limit
        else:
            limit_clause = SQL('')

        async with db(isolation_level=IsolationLevel.REPEATABLE_READ) as conn:
            query = SQL("""
                {query}
                {limit}
            """).format(
                query=SQL(' UNION ALL ').join([
                    SQL("""(
                        SELECT * FROM changeset
                        WHERE {where}
                        AND id BETWEEN {chunk_start} AND {chunk_end}
                        ORDER BY id {order}
                        )""").format(
                        where=where_clause,
                        order=order_clause,
                        chunk_start=PgLiteral(chunk_start),
                        chunk_end=PgLiteral(chunk_end),
                    )
                    for chunk_start, chunk_end in await TimescaleDBQuery.get_chunks_ranges(
                        'changeset', conn, sort=sort
                    )
                ]),
                limit=limit_clause,
            )

            async with await conn.cursor(row_factory=dict_row).execute(
                query, params
            ) as r:
                return await r.fetchall()  # type: ignore

    @staticmethod
    async def count_per_day_by_user(
        user_id: UserId, created_since: datetime
    ) -> dict[date, int]:
        """Count changesets per day by user id since given date."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT created_at::date AS day, COUNT(id)
                FROM changeset
                WHERE user_id = %s AND created_at >= %s
                GROUP BY day
                """,
                (user_id, created_since),
            ) as r,
        ):
            return dict(await r.fetchall())


# === Changeset Comments ===


class ChangesetCommentQuery:
    @staticmethod
    async def count_by_user(user_id: UserId) -> int:
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT COUNT(*) FROM changeset_comment
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def resolve_num_comments(changesets: list[Changeset]) -> None:
        """Resolve the number of comments for each changeset."""
        if not changesets:
            return

        id_map = {changeset['id']: changeset for changeset in changesets}

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT c.value, (
                    SELECT COUNT(*) FROM changeset_comment
                    WHERE changeset_id = c.value
                ) FROM unnest(%s) AS c(value)
                """,
                (list(id_map),),
            ) as r,
        ):
            for changeset_id, count in await r.fetchall():
                id_map[changeset_id]['num_comments'] = count

    @staticmethod
    async def resolve_comments(
        changesets: list[Changeset],
        *,
        limit_per_changeset: int | None,
        resolve_rich_text: bool = False,
    ) -> list[ChangesetComment]:
        """Resolve comments for changesets. Returns the resolved comments."""
        if not changesets:
            return []

        id_map: dict[ChangesetId, list[ChangesetComment]] = {}
        for changeset in changesets:
            id_map[changeset['id']] = changeset['comments'] = []

        query: Query
        params: Params
        if limit_per_changeset is not None:
            # Using window functions to limit comments per changeset
            query = """
            WITH ranked_comments AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY changeset_id ORDER BY id DESC) AS rn
                FROM changeset_comment
                WHERE changeset_id = ANY(%s)
            )
            SELECT * FROM ranked_comments
            WHERE rn <= %s
            ORDER BY changeset_id, id
            """
            params = (list(id_map), limit_per_changeset)
        else:
            # Without limit, just fetch all comments
            query = """
            SELECT * FROM changeset_comment
            WHERE changeset_id = ANY(%s)
            ORDER BY changeset_id, id
            """
            params = (list(id_map),)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            comments: list[ChangesetComment] = await r.fetchall()  # type: ignore

        current_changeset_id: ChangesetId | None = None
        current_comments: list[ChangesetComment] = []

        for comment in comments:
            changeset_id = comment['changeset_id']
            if current_changeset_id != changeset_id:
                current_changeset_id = changeset_id
                current_comments = id_map[changeset_id]
            current_comments.append(comment)

        if limit_per_changeset is None:
            for changeset in changesets:
                changeset['num_comments'] = len(changeset['comments'])  # pyright: ignore [reportTypedDictNotRequiredAccess]

        if resolve_rich_text:
            await changeset_comments_resolve_rich_text(comments)

        return comments


# === Changeset Bounds ===


class ChangesetBoundsQuery:
    @staticmethod
    async def resolve_bounds(changesets: list[Changeset]):
        """Resolve bounds for changesets."""
        if not changesets:
            return

        id_map = {changeset['id']: changeset for changeset in changesets}

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT changeset_id, ST_Collect(bounds)
                FROM changeset_bounds
                WHERE changeset_id = ANY(%s)
                GROUP BY changeset_id
                """,
                (list(id_map),),
            ) as r,
        ):
            rows: list[tuple[ChangesetId, MultiPolygon]] = await r.fetchall()
            for changeset_id, bounds in rows:
                id_map[changeset_id]['bounds'] = bounds
