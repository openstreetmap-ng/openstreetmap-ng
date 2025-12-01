from asyncio import TaskGroup
from typing import Annotated

import orjson
from fastapi import APIRouter, Cookie, File, Form, Query, Response
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.config import COOKIE_AUTH_MAX_AGE, ENV, TIMEZONE_MAX_LENGTH
from app.lib.auth_context import auth_user, web_user
from app.lib.password_hash import PasswordHash
from app.lib.referrer import redirect_referrer
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import User
from app.models.proto.shared_pb2 import PasskeyChallenge
from app.models.types import Email, Password
from app.queries.user_query import UserQuery
from app.services.auth_provider_service import AuthProviderService
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.system_app_service import SystemAppService
from app.services.user_passkey_challenge_service import UserPasskeyChallengeService
from app.services.user_passkey_service import UserPasskeyService
from app.services.user_service import UserService
from app.services.user_signup_service import UserSignupService
from app.services.user_token_email_service import UserTokenEmailService
from app.services.user_token_reset_password_service import UserTokenResetPasswordService
from app.validators.display_name import DisplayNameNormalizing, DisplayNameValidating
from app.validators.email import EmailValidating

router = APIRouter(prefix='/api/web/user')


@router.post('/login')
async def login(
    display_name_or_email: Annotated[
        DisplayNameNormalizing | Email | None, Form(min_length=1)
    ] = None,
    password: Annotated[Password | None, File()] = None,
    passkey: Annotated[bytes | None, File()] = None,
    totp_code: Annotated[str | None, Form(pattern=r'^\d{6}$')] = None,
    recovery_code: Annotated[str | None, Form()] = None,
    remember: Annotated[bool, Form()] = False,
):
    result = await UserService.login(
        display_name_or_email=display_name_or_email,
        password=password,
        passkey=passkey,
        totp_code=totp_code,
        recovery_code=recovery_code,
    )

    # 2FA required
    if isinstance(result, dict):
        return result

    response = Response(None, status.HTTP_204_NO_CONTENT)
    response.set_cookie(
        key='auth',
        value=result.get_secret_value(),
        max_age=int(COOKIE_AUTH_MAX_AGE.total_seconds()) if remember else None,
        secure=ENV != 'dev',
        httponly=True,
        samesite='lax',
    )
    return response


@router.post('/logout')
async def logout(
    auth: Annotated[SecretStr, Cookie()],
    _: Annotated[User, web_user()],
):
    await OAuth2TokenService.revoke_by_access_token(auth)
    response = redirect_referrer()
    response.delete_cookie('auth')
    return response


@router.post('/signup')
async def signup(
    display_name: Annotated[DisplayNameValidating, Form()],
    email: Annotated[EmailValidating, Form()],
    password: Annotated[Password, File()],
    tracking: Annotated[bool, Form()] = False,
    auth_provider_verification: Annotated[str | None, Cookie()] = None,
):
    verification = AuthProviderService.validate_verification(auth_provider_verification)
    email_verified = verification is not None and verification.email == email

    user_id = await UserSignupService.signup(
        display_name=display_name,
        email=email,
        password=password,
        tracking=tracking,
        email_verified=email_verified,
    )
    response = Response(
        orjson.dumps({
            'redirect_url': (
                '/welcome' if email_verified else '/user/account-confirm/pending'
            )
        }),
        media_type='application/json; charset=utf-8',
    )

    if email_verified:
        response.delete_cookie('auth_provider_verification')

    access_token = await SystemAppService.create_access_token(
        SYSTEM_APP_WEB_CLIENT_ID, user_id=user_id
    )
    response.set_cookie(
        key='auth',
        value=access_token.get_secret_value(),
        max_age=None,
        secure=ENV != 'dev',
        httponly=True,
        samesite='lax',
    )

    return response


@router.post('/signup/cancel-provider')
async def signup_cancel_provider():
    response = RedirectResponse('/signup', status.HTTP_303_SEE_OTHER)
    response.delete_cookie('auth_provider_verification')
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

    await UserService.reset_password(
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


@router.post('/timezone')
async def update_timezone(
    timezone: Annotated[str, Form(max_length=TIMEZONE_MAX_LENGTH)],
):
    await UserService.update_timezone(timezone)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/login/passkey/challenge')
async def passkey_challenge(
    display_name_or_email: Annotated[
        DisplayNameNormalizing | Email | None, Form(min_length=1)
    ] = None,
    password: Annotated[Password | None, File()] = None,
):
    user = auth_user()

    if user is None and display_name_or_email is not None and password is not None:
        user = await UserQuery.find_by_display_name_or_email(display_name_or_email)
        if user is not None and not PasswordHash.verify(user, password).success:
            user = None

    async with TaskGroup() as tg:
        challenge_t = tg.create_task(UserPasskeyChallengeService.create())
        credentials = (
            await UserPasskeyService.get_credentials(user['id'])
            if user is not None
            else []
        )

    pb = PasskeyChallenge(
        challenge=challenge_t.result(),
        credentials=credentials,
    )
    if user is not None:
        pb.user_id = user['id']
        pb.user_display_name = user['display_name']
        pb.user_email = user['email']

    return Response(pb.SerializeToString(), media_type='application/x-protobuf')
