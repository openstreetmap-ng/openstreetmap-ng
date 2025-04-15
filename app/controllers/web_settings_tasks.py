import asyncio
from typing import Annotated

from fastapi import APIRouter, Form, Request, Response
from starlette import status

from app.lib.auth_context import web_user
from app.models.db.user import User
from app.services.admin_task_service import AdminTaskService, TaskId

router = APIRouter(prefix='/api/web')


@router.post('/settings/tasks')
async def start_task(
    request: Request,
    _: Annotated[User, web_user('role_administrator')],
    id: Annotated[TaskId, Form()],
):
    # Extract arguments from form data
    args = {
        key[4:]: value
        for key, value in (await request.form()).items()
        if key.startswith('arg_') and isinstance(value, str) and value
    }

    asyncio.create_task(AdminTaskService.start_task(id, args))  # noqa: RUF006
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.get('/settings/tasks/status')
async def task_status(
    _: Annotated[User, web_user('role_administrator')],
):
    return await AdminTaskService.list_tasks()
