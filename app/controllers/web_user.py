from typing import Annotated

import orjson
from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from fastapi import APIRouter, Cookie, Form, Query, Response
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.config import TEST_ENV
from app.lib.auth_context import web_user
from app.lib.redirect_referrer import redirect_referrer
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.limits import COOKIE_AUTH_MAX_AGE, DISPLAY_NAME_MAX_LENGTH
from app.models.db.user import User, UserStatus
from app.models.types import DisplayNameType, EmailType, PasswordType, ValidatingDisplayNameType
from app.services.auth_provider_service import AuthProviderService
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.reset_password_service import ResetPasswordService
from app.services.user_service import UserService
from app.services.user_signup_service import UserSignupService
from app.services.user_token_account_confirm_service import UserTokenAccountConfirmService
from app.validators.email import ValidatingEmailType

router = APIRouter(prefix='/api/web/user')


@router.post('/login')
async def login(
    display_name_or_email: Annotated[
        DisplayNameType | EmailType, Form(min_length=1, max_length=max(DISPLAY_NAME_MAX_LENGTH, EMAIL_MAX_LENGTH))
    ],
    password: Annotated[PasswordType, Form()],
    remember: Annotated[bool, Form()] = False,
):
    access_token = await UserService.login(
        display_name_or_email=display_name_or_email,
        password=password,
    )
    max_age = COOKIE_AUTH_MAX_AGE if remember else None
    response = Response()
    response.set_cookie(
        key='auth',
        value=access_token.get_secret_value(),
        max_age=max_age,
        secure=not TEST_ENV,
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
    display_name: Annotated[ValidatingDisplayNameType, Form()],
    email: Annotated[ValidatingEmailType, Form()],
    password: Annotated[PasswordType, Form()],
    tracking: Annotated[bool, Form()] = False,
    auth_provider_verification: Annotated[str | None, Cookie()] = None,
):
    verification = AuthProviderService.validate_verification(auth_provider_verification)
    email_confirmed = (verification is not None) and verification.email == email
    access_token = await UserSignupService.signup(
        display_name=display_name,
        email=email,
        password=password,
        tracking=tracking,
        email_confirmed=email_confirmed,
    )
    redirect_url = '/welcome' if email_confirmed else '/user/account-confirm/pending'
    response = Response(
        orjson.dumps({'redirect_url': redirect_url}),
        media_type='application/json; charset=utf-8',
    )
    if email_confirmed:
        response.delete_cookie('auth_provider_verification')
    response.set_cookie(
        key='auth',
        value=access_token.get_secret_value(),
        max_age=None,
        secure=not TEST_ENV,
        httponly=True,
        samesite='lax',
    )
    return response


@router.get('/account-confirm')
async def account_confirm(
    token: Annotated[str, Query(min_length=1)],
):
    # TODO: check errors
    token_struct = UserTokenStructUtils.from_str(token)
    await UserTokenAccountConfirmService.confirm(token_struct)
    return RedirectResponse('/welcome', status.HTTP_303_SEE_OTHER)


@router.post('/account-confirm/resend')
async def account_confirm_resend(
    user: Annotated[User, web_user()],
):
    if user.status != UserStatus.pending_activation:
        return {'is_active': True}
    await UserSignupService.send_confirm_email()
    feedback = StandardFeedback()
    feedback.success(None, t('confirmations.resend_success_flash.confirmation_sent', email=user.email))
    return feedback.result


@router.post('/reset-password')
async def reset_password(
    email: Annotated[EmailType, Form()],
):
    await ResetPasswordService.send_reset_link(email)
    feedback = StandardFeedback()
    feedback.success(None, t('settings.password_reset_link_sent'))
    return feedback.result
