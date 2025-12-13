from asyncio import TaskGroup
from typing import Annotated, Literal

from fastapi import APIRouter, Form, Query, Response
from pydantic import NonNegativeInt
from starlette import status

from app.config import (
    REPORT_COMMENT_BODY_MAX_LENGTH,
    REPORT_COMMENTS_PAGE_SIZE,
    REPORT_LIST_PAGE_SIZE,
)
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.lib.standard_feedback import StandardFeedback
from app.lib.standard_pagination import sp_apply_headers, sp_resolve_page
from app.lib.translation import t
from app.models.db.report import ReportType, ReportTypeId
from app.models.db.report_comment import (
    ReportAction,
    ReportActionId,
    ReportCategory,
    report_comments_resolve_rich_text,
)
from app.models.db.user import User, UserRole
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


@router.post('/{report_id:int}/comments')
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


@router.get('')
async def reports_page(
    _: Annotated[User, web_user('role_moderator')],
    page: Annotated[NonNegativeInt, Query()],
    num_items: Annotated[int | None, Query()] = None,
    status: Annotated[Literal['', 'open', 'closed'], Query()] = '',
):
    """Get a page of reports for the moderation interface."""
    # Convert status to boolean for query
    open = None if not status else status == 'open'

    sp_request_headers = num_items is None
    if sp_request_headers:
        num_items = await ReportQuery.count_all(open=open)

    assert num_items is not None
    page = sp_resolve_page(
        page=page, num_items=num_items, page_size=REPORT_LIST_PAGE_SIZE
    )
    reports = await ReportQuery.find_reports_page(
        page=page,
        num_items=num_items,
        open=open,
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

    response = await render_response('reports/reports-page', {'reports': reports})
    if sp_request_headers:
        sp_apply_headers(response, num_items=num_items, page_size=REPORT_LIST_PAGE_SIZE)
    return response


@router.get('/{report_id:int}/comments')
async def comments_page(
    _: Annotated[User, web_user('role_moderator')],
    report_id: ReportId,
    page: Annotated[NonNegativeInt, Query()],
    num_items: Annotated[int | None, Query()] = None,
):
    """Get a page of comments for a specific report."""
    sp_request_headers = num_items is None
    if sp_request_headers:
        num_items = await ReportCommentQuery.count_by_report(report_id)

    assert num_items is not None
    page = sp_resolve_page(
        page=page, num_items=num_items, page_size=REPORT_COMMENTS_PAGE_SIZE
    )
    async with TaskGroup() as tg:
        report_task = tg.create_task(ReportQuery.find_by_id(report_id))
        comments_task = tg.create_task(
            ReportCommentQuery.find_comments_page(
                report_id, page=page, num_items=num_items
            )
        )

    report = await report_task
    assert report is not None
    comments = await comments_task

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

    response = await render_response(
        'reports/comments-page',
        {
            'report': report,
            'comments': comments,
        },
    )
    if sp_request_headers:
        sp_apply_headers(
            response,
            num_items=num_items,
            page_size=REPORT_COMMENTS_PAGE_SIZE,
        )
    return response
