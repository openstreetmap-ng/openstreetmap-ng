from typing import Annotated, Literal

from fastapi import APIRouter, Form

from app.lib.auth_context import web_user
from app.models.db.user import User
from app.services.system_app_service import SystemAppService

router = APIRouter(prefix='/api/web/system-app')


@router.post('/create-access-token')
async def create_access_token(
    client_id: Annotated[Literal['SystemApp.id', 'SystemApp.rapid'], Form()],
    _: Annotated[User, web_user()],
):
    access_token = await SystemAppService.create_access_token(client_id)
    return {'access_token': access_token}
