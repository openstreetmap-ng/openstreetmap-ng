from typing import Annotated, Literal

from fastapi import APIRouter, Form, Response, UploadFile
from starlette import status
from starlette.responses import RedirectResponse

from app.config import USER_DESCRIPTION_MAX_LENGTH
from app.lib.auth_context import web_user
from app.lib.image import UserAvatarType
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.db.connected_account import AuthProvider
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import Editor, User
from app.models.types import LocaleCode, Password
from app.services.auth_service import AuthService
from app.services.connected_account_service import ConnectedAccountService
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.user_service import UserService
from app.services.user_totp_service import UserTOTPService
from app.validators.display_name import DisplayNameValidating
from app.validators.email import EmailValidating
from app.validators.totp_code import TOTPCodeValidating

router = APIRouter(prefix='/api/web')


@router.post('/settings')
async def settings(
    _: Annotated[User, web_user()],
    display_name: Annotated[DisplayNameValidating, Form()],
    language: Annotated[LocaleCode, Form()],
    activity_tracking: Annotated[bool, Form()] = False,
    crash_reporting: Annotated[bool, Form()] = False,
):
    await UserService.update_settings(
        display_name=display_name,
        language=language,
        activity_tracking=activity_tracking,
        crash_reporting=crash_reporting,
    )
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/settings/editor')
async def settings_editor(
    editor: Annotated[Editor | None, Form()],
    _: Annotated[User, web_user()],
):
    await UserService.update_editor(editor=editor)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/settings/avatar')
async def settings_avatar(
    _: Annotated[User, web_user()],
    avatar_type: Annotated[UserAvatarType | Literal[''], Form()],
    avatar_file: Annotated[UploadFile, Form()],
):
    avatar_url = await UserService.update_avatar(avatar_type or None, avatar_file)
    return {'avatar_url': avatar_url}


@router.post('/settings/background')
async def settings_background(
    _: Annotated[User, web_user()],
    background_file: Annotated[UploadFile, Form()],
):
    background_url = await UserService.update_background(background_file)
    return {'background_url': background_url}


@router.post('/settings/email')
async def settings_email(
    _: Annotated[User, web_user()],
    email: Annotated[EmailValidating, Form()],
    password: Annotated[Password, Form()],
):
    await UserService.update_email(
        new_email=email,
        password=password,
    )
    return StandardFeedback.info_result(
        None, t('settings.email_change_confirmation_sent')
    )


@router.post('/settings/password')
async def settings_password(
    _: Annotated[User, web_user()],
    old_password: Annotated[Password, Form()],
    new_password: Annotated[Password, Form()],
    revoke_other_sessions: Annotated[bool, Form()] = False,
):
    await UserService.update_password(
        old_password=old_password,
        new_password=new_password,
    )

    if revoke_other_sessions:
        current_session = await AuthService.authenticate_oauth2(None)
        assert current_session is not None
        await OAuth2TokenService.revoke_by_client_id(
            SYSTEM_APP_WEB_CLIENT_ID, skip_ids=[current_session['id']]
        )

    return StandardFeedback.success_result(
        None, t('settings.password_has_been_changed')
    )


@router.post('/settings/totp/setup')
async def settings_totp_setup(
    _: Annotated[User, web_user()],
    secret: Annotated[str, Form()],
    code: Annotated[TOTPCodeValidating, Form()],
):
    """Set up TOTP 2FA for the current user."""
    await UserTOTPService.setup_totp(secret=secret, code=code)
    return StandardFeedback.success_result(
        None, t('two_fa.two_factor_authentication_is_enabled')
    )


@router.post('/settings/totp/remove')
async def settings_totp_remove(
    _: Annotated[User, web_user()],
    password: Annotated[Password, Form()],
):
    """Remove TOTP 2FA for the current user."""
    await UserTOTPService.remove_totp(password=password)
    return StandardFeedback.success_result(
        None, t('two_fa.two_factor_authentication_has_been_disabled')
    )


@router.post('/settings/description')
async def settings_description(
    _: Annotated[User, web_user()],
    description: Annotated[str, Form(max_length=USER_DESCRIPTION_MAX_LENGTH)],
):
    await UserService.update_description(description=description)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/settings/connections/{provider:str}/disconnect')
async def settings_connections(
    _: Annotated[User, web_user()],
    provider: AuthProvider,
):
    await ConnectedAccountService.remove_connection(provider)
    return RedirectResponse('/settings/connections', status.HTTP_303_SEE_OTHER)
