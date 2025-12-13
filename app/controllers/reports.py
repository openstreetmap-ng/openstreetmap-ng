from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query
from starlette import status

from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.user import User
from app.models.types import ReportId
from app.queries.report_query import ReportQuery
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/reports')
async def reports_index(
    _: Annotated[User, web_user('role_moderator')],
    status: Annotated[Literal['', 'open', 'closed'], Query()] = '',
):
    return await render_response(
        'reports/index',
        {
            'status': status,
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

    if report['type'] == 'user':
        await UserQuery.resolve_users(
            reports,
            user_id_key='type_id',
            user_key='reported_user',
        )

    return await render_response(
        'reports/show',
        {
            'report': report,
        },
    )
