from typing import Annotated

from fastapi import APIRouter, Form, Query, Request, UploadFile
from starlette import status
from starlette.responses import RedirectResponse

from app.config import TEST_ENV
from app.lib.auth_context import web_user
from app.lib.message_collector import MessageCollector
from app.lib.redirect_referrer import redirect_referrer
from app.lib.translation import t
from app.limits import COOKIE_AUTH_MAX_AGE
from app.models.avatar_type import AvatarType
from app.models.db.user import User
from app.models.editor import Editor
from app.models.msgspec.user_token_struct import UserTokenStruct
from app.models.str import DisplayNameStr, EmailStr, PasswordStr
from app.models.user_status import UserStatus
from app.queries.user_query import UserQuery
from app.responses.osm_response import OSMResponse
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.user_signup_service import UserSignupService
from app.services.user_token_account_confirm_service import UserTokenAccountConfirmService

router = APIRouter(prefix='/api/web/user')


# TODO: captcha
# TODO: frontend implement
@router.get('/display-name-available')
async def display_name_available(
    display_name: Annotated[DisplayNameStr, Query()],
):
    return await UserQuery.check_display_name_available(display_name)


@router.post('/login')
async def login(
    display_name_or_email: Annotated[str, Form()],
    password: Annotated[PasswordStr, Form()],
    remember: Annotated[bool, Form()] = False,
):
    collector = MessageCollector()
    token = await UserService.login(
        collector,
        display_name_or_email=display_name_or_email,
        password=password,
    )
    max_age = COOKIE_AUTH_MAX_AGE if remember else None
    response = OSMResponse.serialize(collector.result)
    response.set_cookie('auth', str(token), max_age, secure=not TEST_ENV, httponly=True, samesite='lax')
    return response


@router.post('/logout')
async def logout(
    request: Request,
    _: Annotated[User, web_user()],
):
    token_struct = UserTokenStruct.from_str(request.cookies['auth'])
    await AuthService.destroy_session(token_struct)
    response = redirect_referrer()  # TODO: auto redirect instead of unauthorized for web user
    response.delete_cookie('auth')
    return response


@router.post('/signup')
async def signup(
    display_name: Annotated[DisplayNameStr, Form()],
    email: Annotated[EmailStr, Form()],
    password: Annotated[PasswordStr, Form()],
    tracking: Annotated[bool, Form()],
):
    collector = MessageCollector()
    token = await UserSignupService.signup(
        collector,
        display_name=display_name,
        email=email,
        password=password,
        tracking=tracking,
    )
    response = OSMResponse.serialize(collector.result)
    response.set_cookie('auth', str(token), None, secure=not TEST_ENV, httponly=True, samesite='lax')
    return response


@router.post('/accept-terms')
async def accept_terms(
    _: Annotated[User, web_user()],
):
    await UserSignupService.accept_terms()
    return RedirectResponse('/user/account-confirm/pending', status.HTTP_303_SEE_OTHER)


@router.post('/abort-signup')
async def abort_signup(
    _: Annotated[User, web_user()],
):
    await UserSignupService.abort_signup()
    response = RedirectResponse('/', status.HTTP_303_SEE_OTHER)
    response.delete_cookie('auth')
    return response


@router.get('/account-confirm')
async def account_confirm(
    token: Annotated[str, Query(min_length=1)],
):
    # TODO: check errors
    token_struct = UserTokenStruct.from_str(token)
    await UserTokenAccountConfirmService.confirm(token_struct)
    return RedirectResponse('/welcome', status.HTTP_303_SEE_OTHER)


@router.post('/account-confirm/resend')
async def account_confirm_resend(
    user: Annotated[User, web_user()],
):
    if user.status != UserStatus.pending_activation:
        return {'is_active': True}
    await UserSignupService.send_confirm_email()
    collector = MessageCollector()
    collector.success(None, t('confirmations.resend_success_flash.confirmation_sent', email=user.email))
    return collector.result


@router.post('/settings')
async def update_settings(
    display_name: Annotated[DisplayNameStr, Form()],
    editor: Annotated[Editor | None, Form()],
    language: Annotated[str, Form()],
    activity_tracking: Annotated[bool, Form()],
    crash_reporting: Annotated[bool, Form()],
    _: Annotated[User, web_user()],
):
    collector = MessageCollector()
    await UserService.update_settings(
        collector,
        display_name=display_name,
        editor=editor,
        language=language,
        activity_tracking=activity_tracking,
        crash_reporting=crash_reporting,
    )
    return collector.result


@router.post('/settings/avatar')
async def settings_avatar(
    _: Annotated[User, web_user()],
    avatar_type: Annotated[AvatarType, Form()],
    avatar_file: Annotated[UploadFile | None, Form()] = None,
):
    avatar_url = await UserService.update_avatar(avatar_type, avatar_file)
    return {'avatar_url': avatar_url}
