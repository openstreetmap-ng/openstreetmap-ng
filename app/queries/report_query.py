from typing import NamedTuple, Any

from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.config import REPORT_LIST_PAGE_SIZE
from app.db import db
from app.lib.standard_pagination import standard_pagination_range, generate_pagination_cursors
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
        conditions: list[Composable] = []

        if open or open is None:
            conditions.append(SQL('closed_at IS NULL'))
        if not open:
            conditions.append(SQL('closed_at IS NOT NULL'))

        query = SQL('SELECT COUNT(*) FROM report WHERE {}').format(
            SQL(' OR ').join(conditions)
        )

        async with db() as conn, await conn.execute(query) as r:
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def find_reports_page(
        *,
        page: int,
        num_items: int,
        open: bool | None = None,
    ) -> list[Report]:
        """Get a page of reports for the list view."""
        stmt_limit, stmt_offset = standard_pagination_range(
            page,
            page_size=REPORT_LIST_PAGE_SIZE,
            num_items=num_items,
        )

        conditions: list[Composable] = []

        if open or open is None:
            conditions.append(SQL('closed_at IS NULL'))
        if not open:
            conditions.append(SQL('closed_at IS NOT NULL'))

        # Use DESC ordering for newest first, then reverse for final result
        query = SQL("""
            SELECT * FROM (
                SELECT * FROM report
                WHERE {}
                ORDER BY updated_at DESC
                OFFSET %s
                LIMIT %s
            ) AS subquery
            ORDER BY updated_at ASC
        """).format(SQL(' OR ').join(conditions))

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                query, (stmt_offset, stmt_limit)
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_reports_cursor(
        *,
        after: ReportId | None = None,
        before: ReportId | None = None, 
        limit: int = REPORT_LIST_PAGE_SIZE,
        open: bool | None = None,
    ) -> list[Report]:
        """Get reports using cursor-based pagination."""
        conditions: list[Composable] = []
        params: list[Any] = []

        # Filter by open/closed status
        if open or open is None:
            conditions.append(SQL('closed_at IS NULL'))
        if not open:
            conditions.append(SQL('closed_at IS NOT NULL'))
        
        # Add cursor conditions
        if after is not None:
            conditions.append(SQL('id > %s'))
            params.append(after)
        
        if before is not None:
            conditions.append(SQL('id < %s'))
            params.append(before)

        where_clause = SQL(' AND ').join(conditions) if conditions else SQL('TRUE')
        
        # Always order by updated_at DESC for most recent first, then by id for consistency
        query = SQL("""
            SELECT * FROM report
            WHERE {}
            ORDER BY updated_at DESC, id DESC
            LIMIT %s
        """).format(where_clause)
        
        params.append(limit)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def generate_report_cursors(
        *, 
        open: bool | None = None,
        page_size: int = REPORT_LIST_PAGE_SIZE
    ) -> list[ReportId]:
        """Generate cursor values for reports pagination."""
        conditions: list[Composable] = []

        if open or open is None:
            conditions.append(SQL('closed_at IS NULL'))
        if not open:
            conditions.append(SQL('closed_at IS NOT NULL'))

        where_clause = SQL(' AND ').join(conditions) if conditions else SQL('TRUE')
        
        query = SQL("""
            SELECT id FROM report
            WHERE {}
            ORDER BY updated_at DESC, id DESC
        """).format(where_clause)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query) as r,
        ):
            reports = await r.fetchall()  # type: ignore
            return generate_pagination_cursors(reports, cursor_field='id', page_size=page_size)
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
