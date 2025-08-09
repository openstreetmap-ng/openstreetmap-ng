import cython
from psycopg.rows import dict_row

from app.config import REPORT_COMMENTS_PAGE_SIZE
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.standard_pagination import standard_pagination_range
from app.models.db.report import Report
from app.models.db.report_comment import ReportComment
from app.models.db.user import user_is_admin
from app.models.types import ReportCommentId, ReportId
from app.queries.user_query import UserQuery


class ReportCommentQuery:
    @staticmethod
    async def find_one_by_id(
        report_comment_id: ReportCommentId,
    ) -> ReportComment | None:
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM report_comment
                WHERE id = %s
                """,
                (report_comment_id,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def get_comments_page(
        report_id: ReportId,
        *,
        page: int,
        num_items: int,
    ) -> list[ReportComment]:
        stmt_limit, stmt_offset = standard_pagination_range(
            page,
            page_size=REPORT_COMMENTS_PAGE_SIZE,
            num_items=num_items,
        )

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM (
                    SELECT * FROM report_comment
                    WHERE report_id = %s
                    ORDER BY created_at DESC
                    OFFSET %s
                    LIMIT %s
                ) AS subquery
                ORDER BY created_at ASC
                """,
                (report_id, stmt_offset, stmt_limit),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def resolve_comments(
        reports: list[Report],
        *,
        per_report_limit: int | None = None,
    ) -> list[ReportComment]:
        """Resolve comments for reports. Returns the resolved comments."""
        if not reports:
            return []

        user = auth_user()
        id_map: dict[ReportId, list[ReportComment]] = {}
        for report in reports:
            id_map[report['id']] = report['comments'] = []

        if per_report_limit is not None:
            # Using window functions to limit comments per report (get last N comments)
            query = """
            WITH ranked_comments AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY report_id ORDER BY created_at DESC) AS rn
                FROM report_comment
                WHERE report_id = ANY(%s)
            )
            SELECT * FROM ranked_comments
            WHERE rn <= %s
            ORDER BY report_id, created_at ASC
            """
            params = (list(id_map), per_report_limit)
        else:
            # Without limit, just fetch all comments
            query = """
            SELECT * FROM report_comment
            WHERE report_id = ANY(%s)
            ORDER BY report_id, created_at ASC
            """
            params = (list(id_map),)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            comments: list[ReportComment] = await r.fetchall()  # type: ignore

        # Resolve user information for comments
        await UserQuery.resolve_users(comments)

        is_admin: cython.bint = user_is_admin(user)
        current_report_id: ReportId | None = None
        current_comments: list[ReportComment] = []

        for comment in comments:
            # Mark if comment is restricted from current user
            comment['is_restricted'] = (
                comment['visible_to'] == 'administrator' and not is_admin
            )

            report_id = comment['report_id']
            if current_report_id != report_id:
                current_report_id = report_id
                current_comments = id_map[report_id]
            current_comments.append(comment)

        # Set num_comments for each report if not limiting
        if per_report_limit is None:
            for report in reports:
                report['num_comments'] = len(report['comments'])  # pyright: ignore [reportTypedDictNotRequiredAccess]

        return comments

    @staticmethod
    async def resolve_num_comments(reports: list[Report]) -> None:
        """Resolve the number of comments for each report."""
        if not reports:
            return

        id_map = {report['id']: report for report in reports}

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT c.value, (
                    SELECT COUNT(*) FROM report_comment
                    WHERE report_id = c.value
                ) FROM unnest(%s) AS c(value)
                """,
                (list(id_map),),
            ) as r,
        ):
            for report_id, count in await r.fetchall():
                id_map[report_id]['num_comments'] = count
