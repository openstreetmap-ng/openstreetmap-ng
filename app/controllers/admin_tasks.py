from typing import Annotated

from fastapi import APIRouter

from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.user import User
from app.services.admin_task_service import AdminTaskService

router = APIRouter()


@router.get('/admin/tasks')
async def tasks(
    _: Annotated[User, web_user('role_administrator')],
):
    tasks = await AdminTaskService.list_tasks()

    return await render_response('admin/tasks', {'tasks': tasks})
