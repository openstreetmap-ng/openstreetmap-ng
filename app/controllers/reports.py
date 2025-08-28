from asyncio import TaskGroup
from math import ceil
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query
from starlette import status

from app.config import REPORT_COMMENTS_PAGE_SIZE, REPORT_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.user import User
from app.models.types import ReportId
from app.queries.report_comment_query import ReportCommentQuery
from app.queries.report_query import ReportQuery
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/reports')
async def reports_index(
    _: Annotated[User, web_user('role_moderator')],
    status: Annotated[Literal['', 'open', 'closed'], Query()] = '',
):
    # Convert status to boolean for query
    open = None if not status else status == 'open'

    # Count total reports for pagination
    reports_num_items = await ReportQuery.count_all(open=open)
    reports_num_pages = ceil(reports_num_items / REPORT_LIST_PAGE_SIZE)

    return await render_response(
        'reports/index',
        {
            'status': status,
            'reports_num_items': reports_num_items,
            'reports_num_pages': reports_num_pages,
        },
    )


@router.get('/reports/{report_id:int}')
async def report_show(
    _: Annotated[User, web_user('role_moderator')],
    report_id: Annotated[ReportId, Path()],
):
    report = await ReportQuery.find_by_id(report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Report not found')

    reports = [report]

    # Load comments and count in parallel
    async with TaskGroup() as tg:
        tg.create_task(ReportCommentQuery.resolve_num_comments(reports))

        # Resolve reported user for user-type reports
        if report['type'] == 'user':
            tg.create_task(
                UserQuery.resolve_users(
                    reports,
                    user_id_key='type_id',
                    user_key='reported_user',
                )
            )

    comments_num_items = report['num_comments']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    comments_num_pages = ceil(comments_num_items / REPORT_COMMENTS_PAGE_SIZE)

    return await render_response(
        'reports/show',
        {
            'report': report,
            'comments_num_items': comments_num_items,
            'comments_num_pages': comments_num_pages,
        },
    )
