from typing import Annotated

from fastapi import APIRouter, Cookie, Query
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import web_user
from app.lib.cookie import delete_auth_cookie
from app.lib.referrer import redirect_referrer
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.user import User
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.user_token_email_service import UserTokenEmailService

router = APIRouter(prefix='/api/web/user')


@router.post('/logout')
async def logout(
    auth: Annotated[SecretStr, Cookie()],
    _: Annotated[User, web_user()],
):
    await OAuth2TokenService.revoke_by_access_token(auth)
    response = redirect_referrer()
    delete_auth_cookie(response)
    return response


@router.get('/account-confirm')
async def account_confirm(
    token: Annotated[SecretStr, Query(min_length=1)],
):
    # TODO: check errors
    token_struct = UserTokenStructUtils.from_str(token)
    await UserTokenEmailService.confirm(token_struct, is_account_confirm=True)
    return RedirectResponse('/welcome', status.HTTP_303_SEE_OTHER)


@router.get('/email-change-confirm')
async def email_change_confirm(
    token: Annotated[SecretStr, Query(min_length=1)],
):
    # TODO: check errors
    token_struct = UserTokenStructUtils.from_str(token)
    await UserTokenEmailService.confirm(token_struct, is_account_confirm=False)
    return RedirectResponse('/settings', status.HTTP_303_SEE_OTHER)
