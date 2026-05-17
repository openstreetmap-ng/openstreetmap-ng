from datetime import date, datetime
from string.templatelib import Template
from typing import Literal

from psycopg import AsyncConnection, IsolationLevel
from psycopg.sql import SQL
from shapely import MultiPolygon
from shapely.geometry.base import BaseGeometry

from app.db import (
    db,
    db_count,
    db_fetchall,
    db_fetchone,
    db_fetchrow,
    db_fetchrows,
    t_and,
    t_order,
)
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import (
    ChangesetComment,
    changeset_comments_resolve_rich_text,
)
from app.models.types import ChangesetId, UserId
from app.queries.timescaledb_query import TimescaleDBQuery

_UNION_ALL = SQL(' UNION ALL ')


class ChangesetQuery:
    @staticmethod
    async def find_by_ids(changeset_ids: list[ChangesetId]) -> list[Changeset]:
        """Find changesets by ids."""
        if not changeset_ids:
            return []
        return await db_fetchall(
            Changeset,
            t"""
                SELECT * FROM changeset
                WHERE id = ANY({changeset_ids})
            """,
        )

    @staticmethod
    async def count_by_user(user_id: UserId) -> int:
        """Count changesets by user id."""
        return await db_count('changeset', where={'user_id': user_id})

    @staticmethod
    async def find_adjacent_ids(
        changeset_id: ChangesetId, *, user_id: UserId
    ) -> tuple[ChangesetId | None, ChangesetId | None]:
        """Find the user's previous and next changeset ids."""
        row = await db_fetchrow(t"""
            SELECT
            (   SELECT MAX(id) FROM changeset
                WHERE id < {changeset_id} AND user_id = {user_id}),
            (   SELECT MIN(id) FROM changeset
                WHERE id > {changeset_id} AND user_id = {user_id})
        """)
        assert row is not None
        return row

    @staticmethod
    async def find_by_id(
        changeset_id: ChangesetId,
        *,
        conn: AsyncConnection | None = None,
    ) -> Changeset | None:
        """Find a changeset by id."""
        return await db_fetchone(
            Changeset,
            t'SELECT * FROM changeset WHERE id = {changeset_id}',
            for_update=True,
            conn=conn,
        )

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
        if user_ids is not None and not user_ids:
            return []

        geometry_cond: Template | None = None
        if geometry is not None:
            if legacy_geometry:
                geometry_cond = t'union_bounds && {geometry}'
            else:
                geometry_cond = t"""
                    EXISTS (
                        SELECT 1 FROM changeset_bounds
                        WHERE changeset_id = changeset.id
                        AND bounds && {geometry}
                    )
                """

        where_clause = t_and(
            t'id = ANY({changeset_ids})' if changeset_ids is not None else None,
            t'id < {changeset_id_before}' if changeset_id_before is not None else None,
            t'user_id = ANY({user_ids})' if user_ids is not None else None,
            t'created_at < {created_before}' if created_before is not None else None,
            t'created_at > {created_after}' if created_after is not None else None,
            t'closed_at IS NOT NULL AND closed_at >= {closed_after}'
            if closed_after is not None
            else None,
            t'({is_open}::bool IS NULL OR (closed_at IS NULL) = {is_open})',
            geometry_cond,
        )
        order_clause = t_order(sort)

        async with db(isolation_level=IsolationLevel.REPEATABLE_READ) as conn:
            chunks = await TimescaleDBQuery.get_chunks_ranges(
                'changeset', conn, sort=sort
            )
            unions = _UNION_ALL.join([
                t"""(
                    SELECT * FROM changeset
                    WHERE {where_clause:q}
                    AND id BETWEEN {chunk_start} AND {chunk_end}
                    ORDER BY id {order_clause:q}
                )"""
                for chunk_start, chunk_end in chunks
            ])

            return await db_fetchall(
                Changeset,
                t'{unions:q}',
                limit=limit,
                conn=conn,
            )

    @staticmethod
    async def count_per_day_by_user(
        user_id: UserId, created_since: datetime
    ) -> dict[date, int]:
        """Count changesets per day by user id since given date."""
        return dict(
            await db_fetchrows(t"""
                SELECT created_at::date AS day, COUNT(id)
                FROM changeset
                WHERE user_id = {user_id} AND created_at >= {created_since}
                GROUP BY day
            """)
        )


# === Changeset Comments ===


class ChangesetCommentQuery:
    @staticmethod
    async def count_by_user(user_id: UserId) -> int:
        return await db_count('changeset_comment', where={'user_id': user_id})

    @staticmethod
    async def resolve_num_comments(changesets: list[Changeset]) -> None:
        """Resolve the number of comments for each changeset."""
        if not changesets:
            return

        id_map = {changeset['id']: changeset for changeset in changesets}
        ids = list(id_map)

        rows = await db_fetchrows(t"""
            SELECT c.value, (
                SELECT COUNT(*) FROM changeset_comment
                WHERE changeset_id = c.value
            ) FROM unnest({ids}) AS c(value)
        """)
        for changeset_id, count in rows:
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
        ids = list(id_map)

        if limit_per_changeset is not None:
            query = t"""
                WITH ranked_comments AS (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY changeset_id ORDER BY id DESC) AS rn
                    FROM changeset_comment
                    WHERE changeset_id = ANY({ids})
                )
                SELECT * FROM ranked_comments
                WHERE rn <= {limit_per_changeset}
                ORDER BY changeset_id, id
            """
        else:
            query = t"""
                SELECT * FROM changeset_comment
                WHERE changeset_id = ANY({ids})
                ORDER BY changeset_id, id
            """

        comments = await db_fetchall(ChangesetComment, query)

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
        ids = list(id_map)

        rows: list[tuple[ChangesetId, MultiPolygon]] = await db_fetchrows(t"""
            SELECT changeset_id, ST_Collect(bounds)
            FROM changeset_bounds
            WHERE changeset_id = ANY({ids})
            GROUP BY changeset_id
        """)
        for changeset_id, bounds in rows:
            id_map[changeset_id]['bounds'] = bounds
