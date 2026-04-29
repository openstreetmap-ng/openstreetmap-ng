from typing import Annotated

from fastapi import APIRouter, Cookie, File, Form, Query
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import auth_user, web_user
from app.lib.cookie import delete_auth_cookie
from app.lib.referrer import redirect_referrer
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.user import User
from app.models.types import Email, Password
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.user_password_service import UserPasswordService
from app.services.user_token_email_service import UserTokenEmailService
from app.services.user_token_reset_password_service import UserTokenResetPasswordService

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


@router.post('/account-confirm/resend')
async def account_confirm_resend(
    user: Annotated[User, web_user()],
):
    if user['email_verified']:
        return {'is_active': True}

    await UserTokenEmailService.send_email()
    return StandardFeedback.success_result(
        None,
        t('confirmations.resend_success_flash.confirmation_sent', email=user['email']),
    )


@router.get('/email-change-confirm')
async def email_change_confirm(
    token: Annotated[SecretStr, Query(min_length=1)],
):
    # TODO: check errors
    token_struct = UserTokenStructUtils.from_str(token)
    await UserTokenEmailService.confirm(token_struct, is_account_confirm=False)
    return RedirectResponse('/settings', status.HTTP_303_SEE_OTHER)


@router.post('/reset-password')
async def reset_password(
    email: Annotated[Email, Form()],
):
    await UserTokenResetPasswordService.send_email(email)
    return StandardFeedback.success_result(None, t('settings.password_reset_link_sent'))


@router.post('/reset-password/token')
async def reset_password_token(
    token: Annotated[SecretStr, Form()],
    new_password: Annotated[Password, File()],
):
    revoke_other_sessions = auth_user() is None

    await UserPasswordService.reset_password(
        token=token,
        new_password=new_password,
        revoke_other_sessions=revoke_other_sessions,
    )

    return StandardFeedback.success_result(
        None,
        t('settings.password_reset_success')
        + (
            (' ' + t('settings.password_reset_security_logout'))
            if revoke_other_sessions
            else ''
        ),
    )
