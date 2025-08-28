from asyncio import TaskGroup

import cython
from psycopg.rows import dict_row

from app.config import REPORT_COMMENTS_PAGE_SIZE
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.standard_pagination import standard_pagination_range
from app.models.db.diary import Diary
from app.models.db.message import Message
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.report import Report
from app.models.db.report_comment import ReportComment
from app.models.db.trace import Trace
from app.models.db.user import user_is_admin, user_is_moderator
from app.models.types import (
    ApplicationId,
    DiaryId,
    MessageId,
    ReportCommentId,
    ReportId,
    TraceId,
)
from app.queries.diary_query import DiaryQuery
from app.queries.message_query import MessageQuery
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.trace_query import TraceQuery


class ReportCommentQuery:
    @staticmethod
    async def find_by_id(
        report_comment_id: ReportCommentId,
    ) -> ReportComment | None:
        """Find a report comment by id."""
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
    async def find_comments_page(
        report_id: ReportId,
        *,
        page: int,
        num_items: int,
    ) -> list[ReportComment]:
        """Get a page of comments for a report."""
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
            comments: list[ReportComment] = await r.fetchall()  # type: ignore

        user = auth_user()
        is_moderator: cython.bint = user_is_moderator(user)
        is_admin: cython.bint = user_is_admin(user)

        for comment in comments:
            # Mark if comment is restricted from current user
            comment['has_access'] = (
                (comment['visible_to'] == 'moderator' and is_moderator)  #
                or (comment['visible_to'] == 'administrator' and is_admin)
            )

        return comments

    @staticmethod
    async def resolve_comments(
        reports: list[Report],
        *,
        per_report_limit: int | None = None,
    ) -> list[ReportComment]:
        """Resolve comments for reports."""
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

        is_moderator: cython.bint = user_is_moderator(user)
        is_admin: cython.bint = user_is_admin(user)
        current_report_id: ReportId | None = None
        current_comments: list[ReportComment] = []

        for comment in comments:
            # Mark if comment is restricted from current user
            comment['has_access'] = (
                (comment['visible_to'] == 'moderator' and is_moderator)  #
                or (comment['visible_to'] == 'administrator' and is_admin)
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
    async def resolve_objects(comments: list[ReportComment]) -> None:
        """Resolve objects for report comments."""
        if not comments:
            return

        # Group comments by action type for batch processing
        diary_comments: list[ReportComment] = []
        diary_ids = set[DiaryId]()
        message_comments: list[ReportComment] = []
        message_ids = set[MessageId]()
        app_comments: list[ReportComment] = []
        app_ids = set[ApplicationId]()
        trace_comments: list[ReportComment] = []
        trace_ids = set[TraceId]()

        for comment in comments:
            action = comment['action']
            action_id = comment['action_id']

            if action == 'user_diary':
                diary_comments.append(comment)
                diary_ids.add(action_id)  # type: ignore
            elif action == 'user_message':
                message_comments.append(comment)
                message_ids.add(action_id)  # type: ignore
            elif action == 'user_oauth2_application':
                app_comments.append(comment)
                app_ids.add(action_id)  # type: ignore
            elif action == 'user_trace':
                trace_comments.append(comment)
                trace_ids.add(action_id)  # type: ignore

        # Fetch all object types in parallel
        async with TaskGroup() as tg:
            diary_task = (
                tg.create_task(DiaryQuery.find_by_ids(list(diary_ids)))
                if diary_ids
                else None
            )
            message_task = (
                tg.create_task(MessageQuery.find_by_ids(list(message_ids)))
                if message_ids
                else None
            )
            app_task = (
                tg.create_task(OAuth2ApplicationQuery.find_by_ids(list(app_ids)))
                if app_ids
                else None
            )
            trace_task = (
                tg.create_task(TraceQuery.find_by_ids(list(trace_ids)))
                if trace_ids
                else None
            )

        # Map fetched objects back to comments
        if diary_task is not None:
            diaries = await diary_task
            diary_map: dict[DiaryId, Diary] = {diary['id']: diary for diary in diaries}
            for comment in diary_comments:
                action_id = comment['action_id']
                diary = diary_map.get(action_id)  # type: ignore
                if diary is not None:
                    comment['object'] = diary

        if message_task is not None:
            messages = await message_task
            message_map: dict[MessageId, Message] = {
                message['id']: message for message in messages
            }
            for comment in message_comments:
                action_id = comment['action_id']
                message = message_map.get(action_id)  # type: ignore
                if message is not None:
                    comment['object'] = message

        if app_task is not None:
            apps = await app_task
            app_map: dict[ApplicationId, OAuth2Application] = {
                app['id']: app for app in apps
            }
            for comment in app_comments:
                action_id = comment['action_id']
                app = app_map.get(action_id)  # type: ignore
                if app is not None:
                    comment['object'] = app

        if trace_task is not None:
            traces = await trace_task
            trace_map: dict[TraceId, Trace] = {trace['id']: trace for trace in traces}
            for comment in trace_comments:
                action_id = comment['action_id']
                trace = trace_map.get(action_id)  # type: ignore
                if trace is not None:
                    comment['object'] = trace

    @staticmethod
    async def resolve_num_comments(reports: list[Report]) -> None:
        """Resolve the number of comments for reports."""
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
