from typing import NamedTuple

import cython
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.config import REPORT_LIST_PAGE_SIZE
from app.db import db
from app.lib.standard_pagination import standard_pagination_range
from app.models.db.report import Report
from app.models.db.user import UserRole
from app.models.types import ReportId


class _ReportCountResult(NamedTuple):
    moderator: int
    administrator: int


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
    async def find_reports_page(
        *,
        page: int,
        num_items: int,
        open: bool | None = None,
    ) -> list[Report]:
        """Get a page of reports for the list view."""
        if not num_items:
            return []

        limit, offset = standard_pagination_range(
            page,
            page_size=REPORT_LIST_PAGE_SIZE,
            num_items=num_items,
        )

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                SQL("""
                    SELECT * FROM report
                    WHERE {}
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                """).format(_where_open(open)),
                (limit, offset),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def count_requiring_attention(visible_to: UserRole) -> _ReportCountResult:
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
                0
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
def _where_open(open: bool | None) -> Composable:
    if open is True:
        return SQL('closed_at IS NULL')
    if open is False:
        return SQL('closed_at IS NOT NULL')
    return SQL('TRUE')
