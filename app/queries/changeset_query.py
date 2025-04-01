from datetime import date, datetime
from typing import Literal

from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable
from shapely.geometry.base import BaseGeometry

from app.db import db
from app.models.db.changeset import Changeset
from app.models.types import ChangesetId, UserId


class ChangesetQuery:
    @staticmethod
    async def get_updated_at_by_ids(changeset_ids: list[ChangesetId]) -> dict[ChangesetId, datetime]:
        """Get the updated at timestamp by changeset ids."""
        if not changeset_ids:
            return {}

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT id, updated_at
                FROM changeset
                WHERE id = ANY(%s)
                """,
                (changeset_ids,),
            ) as r,
        ):
            return dict(await r.fetchall())

    @staticmethod
    async def count_by_user_id(user_id: UserId) -> int:
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
    async def get_user_adjacent_ids(
        changeset_id: ChangesetId, *, user_id: UserId
    ) -> tuple[ChangesetId | None, ChangesetId | None]:
        """Get the user's previous and next changeset ids."""
        async with (
            db() as conn,
            await conn.execute(
                """
                (
                    SELECT MAX(id) AS id
                    FROM changeset
                    WHERE id < %(changeset_id)s AND user_id = %(user_id)s
                )
                UNION ALL
                (
                    SELECT MIN(id) AS id
                    FROM changeset
                    WHERE id > %(changeset_id)s AND user_id = %(user_id)s
                )
                """,
                {'changeset_id': changeset_id, 'user_id': user_id},
            ) as r,
        ):
            rows: list[tuple[ChangesetId | None]] = await r.fetchall()
            return rows[0][0], rows[1][0]

    @staticmethod
    async def find_by_id(changeset_id: ChangesetId) -> Changeset | None:
        """Find a changeset by id."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM changeset
                WHERE id = %s
                """,
                (changeset_id,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def find_many_by_query(
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
        params = []

        if changeset_ids is not None:
            conditions.append(SQL('id = ANY(%s)'))
            params.append(changeset_ids)

        if changeset_id_before is not None:
            conditions.append(SQL('id < %s'))
            params.append(changeset_id_before)

        if user_ids is not None:
            if not user_ids:
                return []

            conditions.append(SQL('user_id = ANY(%s)'))
            params.append(user_ids)

        if created_before is not None:
            conditions.append(SQL('created_at < %s'))
            params.append(created_before)

        if created_after is not None:
            conditions.append(SQL('created_at > %s'))
            params.append(created_after)

        if closed_after is not None:
            conditions.append(SQL('closed_at IS NOT NULL AND closed_at >= %s'))
            params.append(closed_after)

        if is_open is not None:
            conditions.append(SQL('closed_at IS NULL') if is_open else SQL('closed_at IS NOT NULL'))

        if geometry is not None:
            # Add union_bounds condition for both legacy and modern queries
            conditions.append(SQL('union_bounds IS NOT NULL AND ST_Intersects(union_bounds, %s)'))
            params.append(geometry)

            # In modern query, add additional filtering on changeset_bounds
            if not legacy_geometry:
                conditions.append(
                    SQL("""
                    EXISTS (
                        SELECT 1 FROM changeset_bounds
                        WHERE changeset_id = changeset.id
                        AND ST_Intersects(bounds, %s)
                    )
                    """)
                )
                params.append(geometry)

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        query = SQL("""
            SELECT * FROM changeset
            WHERE {where}
            ORDER BY id {order}
            {limit}
        """).format(
            where=SQL(' AND ').join(conditions) if conditions else SQL('TRUE'),
            order=SQL(sort),
            limit=limit_clause,
        )

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def count_per_day_by_user_id(user_id: UserId, created_since: datetime) -> dict[date, int]:
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
