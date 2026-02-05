from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Response, UploadFile
from starlette import status
from starlette.responses import RedirectResponse

from app.config import USER_DESCRIPTION_MAX_LENGTH, USER_MAX_SOCIALS
from app.lib.auth_context import web_user
from app.lib.image import UserAvatarType
from app.lib.socials import SOCIALS_CONFIG
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.db.connected_account import AuthProvider
from app.models.db.user import User
from app.models.db.user_profile import UserSocial, UserSocialType
from app.models.types import LocaleCode, Password
from app.services.connected_account_service import ConnectedAccountService
from app.services.user_profile_service import UserProfileService
from app.services.user_service import UserService
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


@router.post('/settings/description')
async def settings_description(
    _: Annotated[User, web_user()],
    description: Annotated[str, Form(max_length=USER_DESCRIPTION_MAX_LENGTH)] = '',
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
