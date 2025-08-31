from typing import Annotated

from fastapi import APIRouter, Form
from starlette import status
from starlette.responses import RedirectResponse

from app.config import ENV
from app.lib.auth_context import web_user
from app.lib.standard_feedback import StandardFeedback
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import User, UserRole
from app.models.types import Password, UserId
from app.services.system_app_service import SystemAppService
from app.services.user_service import UserService
from app.validators.display_name import DisplayNameValidating
from app.validators.email import EmailValidating

router = APIRouter(prefix='/api/web/admin/users')


@router.post('/{user_id:int}/update')
async def update_user(
    _: Annotated[User, web_user('role_administrator')],
    user_id: UserId,
    display_name: Annotated[DisplayNameValidating | None, Form()] = None,
    email: Annotated[EmailValidating | None, Form()] = None,
    email_verified: Annotated[bool, Form()] = False,
    roles: Annotated[list[UserRole] | None, Form()] = None,
    new_password: Annotated[Password | None, Form()] = None,
):
    await UserService.admin_update_user(
        user_id=user_id,
        display_name=display_name,
        email=email,
        email_verified=email_verified,
        roles=roles or [],
        new_password=new_password,
    )
    return StandardFeedback.success_result(None, 'User has been updated')


@router.post('/{user_id:int}/login-as')
async def login_as_user(
    _: Annotated[User, web_user('role_administrator')],
    user_id: UserId,
):
    access_token = await SystemAppService.create_access_token(
        SYSTEM_APP_WEB_CLIENT_ID, user_id=user_id
    )

    response = RedirectResponse('/', status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key='auth',
        value=access_token.get_secret_value(),
        max_age=None,
        secure=ENV != 'dev',
        httponly=True,
        samesite='lax',
    )
    return response
