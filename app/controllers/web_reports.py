from asyncio import TaskGroup
from typing import Annotated, Literal

from fastapi import APIRouter, Form, Query, Response
from psycopg.sql import SQL
from starlette import status

from app.config import (
    REPORT_COMMENT_BODY_MAX_LENGTH,
    REPORT_COMMENTS_PAGE_SIZE,
    REPORT_LIST_PAGE_SIZE,
)
from app.lib.auth_context import auth_user, web_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_paginate_table,
    sp_render_response,
)
from app.lib.translation import t
from app.models.db.report import Report, ReportType, ReportTypeId
from app.models.db.report_comment import (
    ReportAction,
    ReportActionId,
    ReportCategory,
    ReportComment,
    report_comments_resolve_rich_text,
)
from app.models.db.user import User, UserRole, user_is_admin, user_is_moderator
from app.models.types import ReportCommentId, ReportId
from app.queries.report_comment_query import ReportCommentQuery
from app.queries.report_query import ReportQuery
from app.queries.user_query import UserQuery
from app.services.report_comment_service import ReportCommentService
from app.services.report_service import ReportService

router = APIRouter(prefix='/api/web/reports')


@router.post('')
async def create_report(
    _: Annotated[User, web_user()],
    type: Annotated[ReportType, Form()],
    type_id: Annotated[ReportTypeId, Form(gt=0)],
    body: Annotated[str, Form(min_length=1, max_length=REPORT_COMMENT_BODY_MAX_LENGTH)],
    category: Annotated[ReportCategory, Form()],
    action: Annotated[ReportAction, Form()],
    action_id: Annotated[ReportActionId, Form(gt=0)] = None,
):
    await ReportService.create_report(
        type=type,
        type_id=type_id,
        action=action,
        action_id=action_id,
        body=body,
        category=category,
    )
    return StandardFeedback.success_result(
        None, t('report.your_report_has_been_received_and_will_be_reviewed_by_our_team')
    )


@router.post('/{report_id:int}/close')
async def close_report(
    _: Annotated[User, web_user('role_moderator')],
    report_id: ReportId,
    body: Annotated[str, Form(max_length=REPORT_COMMENT_BODY_MAX_LENGTH)] = '',
):
    await ReportService.set_state(report_id, body, close=True)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/{report_id:int}/reopen')
async def reopen_report(
    _: Annotated[User, web_user('role_moderator')],
    report_id: ReportId,
    body: Annotated[str, Form(max_length=REPORT_COMMENT_BODY_MAX_LENGTH)] = '',
):
    await ReportService.set_state(report_id, body, close=False)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/{report_id:int}/comment')
async def add_comment(
    _: Annotated[User, web_user('role_moderator')],
    report_id: ReportId,
    body: Annotated[str, Form(min_length=1, max_length=REPORT_COMMENT_BODY_MAX_LENGTH)],
):
    await ReportService.add_comment(report_id, body)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/{__:int}/comments/{comment_id:int}/visibility')
async def change_comment_visibility(
    _: Annotated[User, web_user('role_administrator')],
    __: ReportId,
    comment_id: ReportCommentId,
    visible_to: Annotated[UserRole, Form()],
):
    await ReportCommentService.update_visibility(comment_id, visible_to)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/page')
async def reports_page(
    _: Annotated[User, web_user('role_moderator')],
    status: Annotated[Literal['', 'open', 'closed'], Query()],
    sp_state: StandardPaginationStateBody = b'',
):
    """Get a page of reports for the moderation interface."""
    # Convert status to boolean for query
    open = None if not status else status == 'open'

    if open is True:
        where = SQL('closed_at IS NULL')
    elif open is False:
        where = SQL('closed_at IS NOT NULL')
    else:
        where = SQL('TRUE')

    reports, state = await sp_paginate_table(
        Report,
        sp_state,
        table='report',
        where=where,
        page_size=REPORT_LIST_PAGE_SIZE,
        cursor_column='updated_at',
        cursor_kind='datetime',
        order_dir='desc',
    )

    # Resolve comments and metadata
    async with TaskGroup() as tg:
        # Resolve reported users for user-type reports
        user_reports = [r for r in reports if r['type'] == 'user']
        if user_reports:
            tg.create_task(
                UserQuery.resolve_users(
                    user_reports,
                    user_id_key='type_id',
                    user_key='reported_user',
                )
            )

        tg.create_task(ReportCommentQuery.resolve_num_comments(reports))
        # Get only the last comment for preview
        comments = await ReportCommentQuery.resolve_comments(
            reports, per_report_limit=1
        )
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(report_comments_resolve_rich_text(comments))
        tg.create_task(ReportCommentQuery.resolve_objects(comments))

    return await sp_render_response(
        'reports/reports-page',
        {'reports': reports},
        state,
    )


@router.post('/{report_id:int}/comments')
async def comments_page(
    _: Annotated[User, web_user('role_moderator')],
    report_id: ReportId,
    sp_state: StandardPaginationStateBody = b'',
):
    """Get a page of comments for a specific report."""
    async with TaskGroup() as tg:
        report_task = tg.create_task(ReportQuery.find_by_id(report_id))
        comments_task = tg.create_task(
            sp_paginate_table(
                ReportComment,
                sp_state,
                table='report_comment',
                where=SQL('report_id = %s'),
                params=(report_id,),
                page_size=REPORT_COMMENTS_PAGE_SIZE,
                cursor_column='created_at',
                cursor_kind='datetime',
                order_dir='desc',
                display_dir='asc',
            )
        )

    report = await report_task
    assert report is not None
    comments, state = await comments_task

    user = auth_user()
    is_moderator = user_is_moderator(user)
    is_admin = user_is_admin(user)
    for comment in comments:
        comment['has_access'] = (
            (comment['visible_to'] == 'moderator' and is_moderator)  #
            or (comment['visible_to'] == 'administrator' and is_admin)
        )

    async with TaskGroup() as tg:
        if report['type'] == 'user':
            tg.create_task(
                UserQuery.resolve_users(
                    [report],
                    user_id_key='type_id',
                    user_key='reported_user',
                )
            )
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(report_comments_resolve_rich_text(comments))
        tg.create_task(ReportCommentQuery.resolve_objects(comments))

    return await sp_render_response(
        'reports/comments-page',
        {
            'report': report,
            'comments': comments,
        },
        state,
    )
