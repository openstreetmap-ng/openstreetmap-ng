import logging

import cython
from psycopg import AsyncConnection, IsolationLevel
from zid import zid

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.db.report import ReportInit, ReportType, ReportTypeId
from app.models.db.report_comment import (
    ReportAction,
    ReportActionId,
    ReportCategory,
    ReportCommentInit,
    report_comments_resolve_rich_text,
)
from app.models.db.user import UserRole
from app.models.types import ReportCommentId, ReportId
from app.queries.report_comment_query import ReportCommentQuery
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
                    updated_at = statement_timestamp()
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

        comment = await ReportCommentQuery.find_one_by_id(comment_init['id'])
        assert comment is not None
        comment['user'] = user  # type: ignore
        await report_comments_resolve_rich_text([comment])

        await EmailService.schedule(
            source=None,
            from_user_id=None,
            to_user=user,
            subject=f'[{t("project_name")}] {t("report.email_confirmation.your_report_has_been_received")}',
            template_name='email/report-confirm',
            template_data={'comment': comment},
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
                SET updated_at = statement_timestamp()
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
    async def close_report(report_id: ReportId, body: str) -> None:
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

                if result[0] is not None:
                    StandardFeedback.raise_error(None, 'Report is already closed')

            await conn.execute(
                """
                UPDATE report SET
                    closed_at = statement_timestamp(),
                    updated_at = statement_timestamp()
                WHERE id = %s
                """,
                (report_id,),
            )

            comment_init: ReportCommentInit = {
                'id': zid(),  # type: ignore
                'report_id': report_id,
                'user_id': user_id,
                'action': 'close',
                'action_id': None,
                'body': body,
                'category': None,
                'visible_to': 'moderator',
            }
            await _add_report_comment(conn, comment_init)

        logging.debug('Closed report %d by user %d', report_id, user_id)

    @staticmethod
    async def reopen_report(report_id: ReportId, body: str) -> None:
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

                if result[0] is None:
                    StandardFeedback.raise_error(None, 'Report is already open')

            await conn.execute(
                """
                UPDATE report SET
                    closed_at = NULL,
                    updated_at = statement_timestamp()
                WHERE id = %s
                """,
                (report_id,),
            )

            comment_init: ReportCommentInit = {
                'id': zid(),  # type: ignore
                'report_id': report_id,
                'user_id': user_id,
                'action': 'reopen',
                'action_id': None,
                'body': body,
                'category': None,
                'visible_to': 'moderator',
            }
            await _add_report_comment(conn, comment_init)

        logging.debug('Reopened report %d by user %d', report_id, user_id)

    @staticmethod
    async def change_comment_visibility(
        comment_id: ReportCommentId,
        new_visibility: UserRole,
    ) -> None:
        user = auth_user(required=True)
        user_id = user['id']

        async with db(True) as conn:
            result = await conn.execute(
                """
                UPDATE report_comment SET visible_to = %s
                WHERE id = %s AND visible_to != %s
                """,
                (new_visibility, comment_id, new_visibility),
            )

            if result.rowcount:
                logging.debug(
                    'Changed visibility of comment %d to %r by user %d',
                    comment_id,
                    new_visibility,
                    user_id,
                )


@cython.cfunc
def _category_to_visibility(category: ReportCategory):
    if category == 'privacy':
        return 'administrator'

    # spam, vandalism, harassment, other -> moderator
    return 'moderator'


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
