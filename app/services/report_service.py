import logging
from asyncio import TaskGroup
from typing import Any

import cython
from psycopg import AsyncConnection, IsolationLevel
from zid import zid

from app.config import APP_URL
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import nt, t
from app.models.db.report import ReportInit, ReportType, ReportTypeId
from app.models.db.report_comment import (
    ReportAction,
    ReportActionId,
    ReportCategory,
    ReportCommentInit,
    report_comments_resolve_rich_text,
)
from app.models.types import ReportId
from app.queries.changeset_query import ChangesetQuery
from app.queries.diary_query import DiaryQuery
from app.queries.message_query import MessageQuery
from app.queries.note_query import NoteQuery
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.report_comment_query import ReportCommentQuery
from app.queries.report_query import ReportQuery
from app.queries.trace_query import TraceQuery
from app.queries.user_query import UserQuery
from app.services.email_service import EmailService


class ReportService:
    @staticmethod
    async def create_report(
        *,
        type: ReportType,
        type_id: ReportTypeId,
        action: ReportAction,
        action_id: ReportActionId,
        body: str,
        category: ReportCategory,
    ) -> ReportId:
        if action == 'comment' and not body:
            raise ValueError('Comment body cannot be empty')

        user = auth_user(required=True)
        user_id = user['id']

        await _validate_integrity(type, type_id, action, action_id)

        async with db(True, isolation_level=IsolationLevel.REPEATABLE_READ) as conn:
            report_init: ReportInit = {
                'id': zid(),  # type: ignore
                'type': type,
                'type_id': type_id,
            }

            async with await conn.execute(
                """
                INSERT INTO report (
                    id, type, type_id
                )
                VALUES (
                    %(id)s, %(type)s, %(type_id)s
                )
                ON CONFLICT (type, type_id) DO UPDATE SET
                    closed_at = NULL,
                    updated_at = DEFAULT
                RETURNING id
                """,
                report_init,
            ) as r:
                report_id: ReportId = (await r.fetchone())[0]  # type: ignore

            visible_to = _category_to_visibility(category)
            comment_init: ReportCommentInit = {
                'id': zid(),  # type: ignore
                'report_id': report_id,
                'user_id': user_id,
                'action': action,
                'action_id': action_id,
                'body': body,
                'category': category,
                'visible_to': visible_to,
            }
            await _add_report_comment(conn, comment_init)

        if report_init['id'] == report_id:
            logging.debug(
                'Created new report %d for %s:%d by user %d',
                report_id,
                type,
                type_id,
                user_id,
            )
        else:
            logging.debug('Updated existing report %d by user %d', report_id, user_id)

        logging.debug(
            'Added report comment %d to report %d by user %d',
            comment_init['id'],
            report_id,
            user_id,
        )

        comment = await ReportCommentQuery.find_by_id(comment_init['id'])
        assert comment is not None
        comment['user'] = user  # type: ignore

        async with TaskGroup() as tg:
            comments = [comment]
            tg.create_task(report_comments_resolve_rich_text(comments))
            tg.create_task(ReportCommentQuery.resolve_objects(comments))

            report = await ReportQuery.find_by_id(report_id)
            assert report is not None

        # Resolve user info if needed
        if type == 'user' and action != 'user_account':
            await UserQuery.resolve_users(
                [report],
                user_id_key='type_id',
                user_key='reported_user',
            )

        reported_user = report.get('reported_user')
        reported_content_html: str
        if action == 'user_profile':
            assert reported_user is not None
            reported_content_html = t(
                'report.email_confirmation.you_reported_user_profile_with_the_following_message',
                user=f'<a href="{APP_URL}/user-id/{type_id}">{reported_user["display_name"]}</a>',
            )
        elif action == 'user_account':
            assert reported_user is None
            reported_content_html = t(
                'report.email_confirmation.you_reported_account_problem_with_the_following_message'
            )
        else:
            object_html: str
            if action == 'user_changeset':
                object_html = f'<a href="{APP_URL}/changeset/{action_id}">{nt("changeset.count", 1)} {action_id}</a>'
            elif action == 'user_diary':
                diary = comment.get('object')
                diary_title = (
                    f'“{diary["title"]}”'  # pyright: ignore[reportGeneralTypeIssues]
                    if diary is not None
                    else '«Deleted»'
                )
                object_html = f'<a href="{APP_URL}/diary/{action_id}">{nt("diary.entry.count", 1)} {diary_title}</a>'
            elif action == 'user_message':
                message = comment.get('object')
                message_subject = (
                    f'“{message["subject"]}”'  # pyright: ignore[reportGeneralTypeIssues]
                    if message is not None
                    else '«Deleted»'
                )
                object_html = f'<a href="{APP_URL}/messages/inbox?show={action_id}">{t("activerecord.models.message")} {message_subject}</a>'
            elif action == 'user_note' or type == 'anonymous_note':
                note_id = action_id or type_id
                object_html = f'<a href="{APP_URL}/note/{note_id}">{nt("note.count", 1)} {note_id}</a>'
            elif action == 'user_trace':
                trace = comment.get('object')
                trace_name = (
                    f'“{trace["name"]}”'  # pyright: ignore[reportGeneralTypeIssues]
                    if trace is not None
                    else '«Deleted»'
                )
                object_html = f'<a href="{APP_URL}/trace/{action_id}">{nt("trace.gps_count", 1)} {trace_name}</a>'
            elif action == 'user_oauth2_application':
                app = comment.get('object')
                app_name = (
                    f'“{app["name"]}”'  # pyright: ignore[reportGeneralTypeIssues]
                    if app is not None
                    else '«Deleted»'
                )
                object_html = f'{t("oauth2_authorized_applications.index.application")} {app_name} ({action_id})'
            else:
                raise NotImplementedError(f'Unsupported report action {action!r}')

            # With user info when available
            if reported_user is not None:
                reported_content_html = t(
                    'report.email_confirmation.you_reported_object_by_user_with_the_following_message',
                    object=object_html,
                    user=f'<a href="{APP_URL}/user-id/{type_id}">{reported_user["display_name"]}</a>',
                )
            else:
                reported_content_html = t(
                    'report.email_confirmation.you_reported_object_with_the_following_message',
                    object=object_html,
                )

        template_data: dict[str, Any] = {
            'comment': comment,
            'reported_content_html': reported_content_html,
        }

        await EmailService.schedule(
            source=None,
            from_user_id=None,
            to_user=user,
            subject=f'[{t("project_name")}] {t("report.email_confirmation.your_report_has_been_received")}',
            template_name='email/report-confirm',
            template_data=template_data,
        )

        return report_id

    @staticmethod
    async def add_comment(
        report_id: ReportId,
        body: str,
    ) -> None:
        user = auth_user(required=True)
        user_id = user['id']

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT 1 FROM report
                WHERE id = %s
                FOR UPDATE
                """,
                (report_id,),
            ) as r:
                result = await r.fetchone()
                assert result is not None, f'Report {report_id} not found'

            await conn.execute(
                """
                UPDATE report
                SET updated_at = DEFAULT
                WHERE id = %s
                """,
                (report_id,),
            )

            comment_init: ReportCommentInit = {
                'id': zid(),  # type: ignore
                'report_id': report_id,
                'user_id': user_id,
                'action': 'comment',
                'action_id': None,
                'body': body,
                'category': None,
                'visible_to': 'moderator',
            }
            await _add_report_comment(conn, comment_init)

        logging.debug(
            'Added comment to report %d by user %d',
            report_id,
            user_id,
        )

    @staticmethod
    async def set_state(report_id: ReportId, body: str, *, close: bool) -> None:
        """Close or reopen a report."""
        user = auth_user(required=True)
        user_id = user['id']

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT closed_at FROM report
                WHERE id = %s
                FOR UPDATE
                """,
                (report_id,),
            ) as r:
                result = await r.fetchone()
                assert result is not None, f'Report {report_id} not found'

                is_closed = result[0] is not None
                if close and is_closed:
                    StandardFeedback.raise_error(None, 'Report is already closed')
                if not close and not is_closed:
                    StandardFeedback.raise_error(None, 'Report is already open')

            await conn.execute(
                """
                UPDATE report SET
                    closed_at = CASE WHEN %s THEN statement_timestamp() ELSE NULL END,
                    updated_at = DEFAULT
                WHERE id = %s
                """,
                (close, report_id),
            )

            comment_init: ReportCommentInit = {
                'id': zid(),  # type: ignore
                'report_id': report_id,
                'user_id': user_id,
                'action': 'close' if close else 'reopen',
                'action_id': None,
                'body': body,
                'category': None,
                'visible_to': 'moderator',
            }
            await _add_report_comment(conn, comment_init)

        logging.debug(
            '%s report %d by user %d',
            'Closed' if close else 'Reopened',
            report_id,
            user_id,
        )


@cython.cfunc
def _category_to_visibility(category: ReportCategory):
    if category == 'privacy':
        return 'administrator'

    # spam, vandalism, harassment, other -> moderator
    return 'moderator'


async def _validate_integrity(
    type: ReportType,
    type_id: ReportTypeId,
    action: ReportAction,
    action_id: ReportActionId,
) -> None:
    if type == 'user':
        assert action.startswith('user_')
    elif type == 'anonymous_note':
        assert action == 'generic'
    else:
        raise NotImplementedError(f'Unsupported report type {type!r}')

    if action == 'user_changeset':
        assert action_id is not None
        changeset = await ChangesetQuery.find_by_id(action_id)  # pyright: ignore[reportArgumentType]
        assert changeset is not None and changeset['user_id'] == type_id

    elif action == 'user_diary':
        assert action_id is not None
        diary = await DiaryQuery.find_by_id(action_id)  # pyright: ignore[reportArgumentType]
        assert diary is not None and diary['user_id'] == type_id

    elif action == 'user_message':
        assert action_id is not None
        message = await MessageQuery.get_by_id(action_id)  # pyright: ignore[reportArgumentType]
        assert message['from_user_id'] == type_id

    elif action == 'user_note':
        assert action_id is not None
        note = await NoteQuery.find(
            user_id=type_id,  # pyright: ignore[reportArgumentType]
            event='opened',
            note_ids=[action_id],  # pyright: ignore[reportArgumentType]
            limit=1,
        )
        assert note

    elif action == 'user_oauth2_application':
        assert action_id is not None
        app = await OAuth2ApplicationQuery.find_by_id(action_id, user_id=type_id)  # pyright: ignore[reportArgumentType]
        assert app is not None

    elif action == 'user_trace':
        assert action_id is not None
        trace = await TraceQuery.get_by_id(action_id)  # pyright: ignore[reportArgumentType]
        assert trace['user_id'] == type_id

    else:
        assert action_id is None, f'Report {type}/{action} must not have action_id'


async def _add_report_comment(
    conn: AsyncConnection,
    /,
    comment_init: ReportCommentInit,
) -> None:
    await conn.execute(
        """
        INSERT INTO report_comment (
            id, report_id, user_id,
            action, action_id, body,
            category, visible_to
        )
        VALUES (
            %(id)s, %(report_id)s, %(user_id)s,
            %(action)s, %(action_id)s, %(body)s,
            %(category)s, %(visible_to)s
        )
        """,
        comment_init,
    )
