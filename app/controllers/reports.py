from typing import Annotated

from fastapi import APIRouter, Path

from app.lib.auth_context import web_user
from app.lib.render_response import render_proto_page
from app.models.db.user import User
from app.models.proto.report_pb2 import IndexPage, ShowPage
from app.models.types import ReportId
from app.rpc.report import build_report_header

router = APIRouter()


@router.get('/reports')
async def reports_index(_: Annotated[User, web_user('role_moderator')]):
    return await render_proto_page(IndexPage(), title_prefix='Reports')


@router.get('/reports/{report_id:int}')
async def report_show(
    _: Annotated[User, web_user('role_moderator')],
    report_id: Annotated[ReportId, Path()],
):
    header = await build_report_header(report_id)
    return await render_proto_page(
        ShowPage(report_id=report_id, header=header),
        title_prefix=f'Report {report_id}',
    )
