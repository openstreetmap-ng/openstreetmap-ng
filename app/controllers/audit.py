from typing import Annotated

from fastapi import APIRouter

from app.lib.auth_context import web_user
from app.lib.render_response import render_proto_page
from app.models.db.user import User
from app.models.proto.audit_pb2 import Page

router = APIRouter()


@router.get('/audit')
async def audit_index(_: Annotated[User, web_user('role_administrator')]):
    return await render_proto_page(
        Page(),
        title_prefix='Audit logs',
    )
