from typing import Annotated

from fastapi import APIRouter

from app.lib.auth_context import web_user
from app.lib.render_response import render_proto_page
from app.models.db.user import User
from app.models.proto.admin_tasks_pb2 import Page

router = APIRouter()


@router.get('/admin/tasks')
async def tasks(
    _: Annotated[User, web_user('role_administrator')],
):
    return await render_proto_page(
        Page(),
        title_prefix='Administrative tasks',
    )
