from typing import NamedTuple

import cython
from psycopg.rows import dict_row
from psycopg.sql import SQL

from app.db import db
from app.models.db.report import Report
from app.models.db.user import UserRole
from app.models.types import ReportId


class _ReportCountResult(NamedTuple):
    moderator: int
    administrator: int | None


class ReportQuery:
    @staticmethod
    async def find_by_id(report_id: ReportId) -> Report | None:
        """Find a report by id."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM report
                WHERE id = %s
                """,
                (report_id,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def count_all(*, open: bool | None = None) -> int:
        """Count all reports, optionally filtered by open/closed status."""
        async with (
            db() as conn,
            await conn.execute(
                SQL("""
                    SELECT COUNT(*)
                    FROM report
                    WHERE {}
                """).format(_where_open(open))
            ) as r,
        ):
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def count_requiring_attention(visible_to: UserRole):
        """Count reports requiring attention."""
        # Build query dynamically based on visibility level
        if visible_to == 'administrator':
            select_clause = SQL("""
                COUNT(*) FILTER (
                    WHERE lc.visible_to = 'moderator'
                ),
                COUNT(*) FILTER (
                    WHERE lc.visible_to = 'administrator'
                )
            """)
        else:
            select_clause = SQL("""
                COUNT(*) FILTER (
                    WHERE lc.visible_to = 'moderator'
                ),
                NULL
            """)

        query = SQL("""
            WITH last_comment_ranked AS (
                SELECT
                    rc.action,
                    rc.visible_to,
                    ROW_NUMBER() OVER(PARTITION BY rc.report_id ORDER BY rc.created_at DESC) as rn
                FROM report_comment rc
                JOIN report r ON rc.report_id = r.id
                WHERE r.closed_at IS NULL
            )
            SELECT {}
            FROM last_comment_ranked lc
            WHERE
                lc.rn = 1 AND
                lc.action NOT IN ('comment', 'close', 'reopen')
        """).format(select_clause)

        async with db() as conn, await conn.execute(query) as r:
            return _ReportCountResult(*(await r.fetchone()))  # type: ignore


@cython.cfunc
def _where_open(open: bool | None):
    if open is True:
        return SQL('closed_at IS NULL')
    if open is False:
        return SQL('closed_at IS NOT NULL')
    return SQL('TRUE')
