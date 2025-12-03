from base64 import urlsafe_b64decode
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Response, UploadFile
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.config import (
    PASSKEY_NAME_MAX_LENGTH,
    USER_DESCRIPTION_MAX_LENGTH,
    USER_MAX_SOCIALS,
)
from app.lib.auth_context import web_user
from app.lib.image import UserAvatarType
from app.lib.render_response import render_response
from app.lib.socials import SOCIALS_CONFIG
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.db.connected_account import AuthProvider
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import Editor, User
from app.models.db.user_profile import UserSocial, UserSocialType
from app.models.proto.shared_pb2 import PasskeyRegistration
from app.models.types import LocaleCode, Password
from app.services.auth_service import AuthService
from app.services.connected_account_service import ConnectedAccountService
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.user_passkey_service import UserPasskeyService
from app.services.user_password_service import UserPasswordService
from app.services.user_profile_service import UserProfileService
from app.services.user_recovery_code_service import UserRecoveryCodeService
from app.services.user_service import UserService
from app.services.user_totp_service import UserTOTPService
from app.validators.display_name import DisplayNameValidating
from app.validators.email import EmailValidating

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
    password: Annotated[Password, File()],
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
    old_password: Annotated[Password, File()],
    new_password: Annotated[Password, File()],
    revoke_other_sessions: Annotated[bool, Form()] = False,
):
    await UserPasswordService.update_password(
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
    secret: Annotated[SecretStr, Form()],
    digits: Annotated[Literal['6', '8'], Form()],
    totp_code: Annotated[str, Form(pattern=r'^(?:\d{6}|\d{8})$')],
):
    await UserTOTPService.setup_totp(secret, int(digits), totp_code)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/settings/totp/remove')
async def settings_totp_remove(
    _: Annotated[User, web_user()],
    password: Annotated[Password, File()],
):
    await UserTOTPService.remove_totp(password=password)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/settings/recovery-codes/generate')
async def settings_recovery_codes_generate(
    _: Annotated[User, web_user()],
    password: Annotated[Password, File()],
):
    codes = await UserRecoveryCodeService.generate_recovery_codes(password=password)
    return await render_response(
        'settings/_recovery_codes',
        {'codes': codes},
    )


@router.post('/settings/description')
async def settings_description(
    _: Annotated[User, web_user()],
    description: Annotated[str, Form(max_length=USER_DESCRIPTION_MAX_LENGTH)],
):
    await UserProfileService.update_description(description=description)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/settings/socials')
async def settings_socials(
    _: Annotated[User, web_user()],
    service: Annotated[
        list[UserSocialType], Form(default_factory=list, max_length=USER_MAX_SOCIALS)
    ],
    value: Annotated[
        list[str], Form(default_factory=list, max_length=USER_MAX_SOCIALS)
    ],
):
    socials: list[UserSocial] = []

    for s, v in zip(service, value, strict=True):
        config = SOCIALS_CONFIG.get(s)
        if config is None:
            continue

        v = v.strip()
        if not v:
            continue

        if 'template' not in config and not v.lower().startswith('https://'):
            v = 'https://' + v.split('://', 1)[-1]

        socials.append(UserSocial(s, v))

    await UserProfileService.update_socials(socials=socials)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/settings/connections/{provider:str}/disconnect')
async def settings_connections(
    _: Annotated[User, web_user()],
    provider: AuthProvider,
):
    await ConnectedAccountService.remove_connection(provider)
    return RedirectResponse('/settings/connections', status.HTTP_303_SEE_OTHER)


@router.post('/settings/passkey/register')
async def settings_passkey_register(
    _: Annotated[User, web_user()],
    passkey: Annotated[bytes, File()],
):
    registration = PasskeyRegistration.FromString(passkey)
    await UserPasskeyService.register_passkey(registration)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/settings/passkey/{credential_id_b64:str}/rename')
async def settings_passkey_rename(
    _: Annotated[User, web_user()],
    credential_id_b64: str,
    name: Annotated[str, Form(max_length=PASSKEY_NAME_MAX_LENGTH)],
):
    credential_id = urlsafe_b64decode(credential_id_b64 + '==')
    effective_name = await UserPasskeyService.rename_passkey(credential_id, name=name)
    if effective_name is None:
        return Response(None, status.HTTP_404_NOT_FOUND)
    return {'name': effective_name}


@router.post('/settings/passkey/{credential_id_b64:str}/remove')
async def settings_passkey_remove(
    _: Annotated[User, web_user()],
    credential_id_b64: str,
    password: Annotated[Password, File()],
):
    credential_id = urlsafe_b64decode(credential_id_b64 + '==')
    await UserPasskeyService.remove_passkey(credential_id, password=password)
    return Response(None, status.HTTP_204_NO_CONTENT)
