from typing import Annotated

from fastapi import APIRouter, Form, Path, Response, UploadFile

from app.lib.auth_context import web_user
from app.lib.message_collector import MessageCollector
from app.limits import OAUTH_APP_NAME_MAX_LENGTH
from app.models.db.user import AvatarType, Editor, User
from app.models.types import (
    LocaleCode,
    PasswordType,
    ValidatingDisplayNameType,
    ValidatingEmailType,
    ValidatingPasswordType,
)
from app.services.auth_service import AuthService
from app.services.oauth2_application_service import OAuth2ApplicationService
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.user_service import UserService

router = APIRouter(prefix='/api/web')


@router.post('/settings')
async def settings(
    _: Annotated[User, web_user()],
    display_name: Annotated[ValidatingDisplayNameType, Form()],
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
    return Response()


@router.post('/settings/editor')
async def settings_editor(
    editor: Annotated[Editor | None, Form()],
    _: Annotated[User, web_user()],
):
    await UserService.update_editor(editor=editor)
    return Response()


@router.post('/settings/avatar')
async def settings_avatar(
    _: Annotated[User, web_user()],
    avatar_type: Annotated[AvatarType, Form()],
    avatar_file: Annotated[UploadFile, Form()],
):
    avatar_url = await UserService.update_avatar(avatar_type, avatar_file)
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
    email: Annotated[ValidatingEmailType, Form()],
    password: Annotated[PasswordType, Form()],
):
    collector = MessageCollector()
    await UserService.update_email(collector, new_email=email, password=password)
    return collector.result


@router.post('/settings/password')
async def settings_password(
    _: Annotated[User, web_user()],
    old_password: Annotated[PasswordType, Form()],
    new_password: Annotated[ValidatingPasswordType, Form()],
    revoke_other_sessions: Annotated[bool, Form()] = False,
):
    collector = MessageCollector()
    await UserService.update_password(collector, old_password=old_password, new_password=new_password)
    if revoke_other_sessions:
        current_session = await AuthService.authenticate_oauth2(None)
        await OAuth2TokenService.revoke_by_client_id('SystemApp.web', skip_ids=(current_session.id,))  # pyright: ignore[reportOptionalMemberAccess]
    return collector.result


@router.post('/settings/revoke-token')
async def settings_revoke_token(
    _: Annotated[User, web_user()],
    token_id: Annotated[int, Form()],
):
    await OAuth2TokenService.revoke_by_id(token_id)
    return Response()


@router.post('/settings/revoke-application')
async def settings_revoke_application(
    _: Annotated[User, web_user()],
    application_id: Annotated[int, Form()],
):
    await OAuth2TokenService.revoke_by_app_id(application_id)
    return Response()


@router.post('/settings/applications/admin/create')
async def create_application(
    _: Annotated[User, web_user()],
    name: Annotated[str, Form(min_length=1, max_length=OAUTH_APP_NAME_MAX_LENGTH)],
):
    app_id = await OAuth2ApplicationService.create(name=name)
    return {'redirect_url': f'/settings/applications/admin/{app_id}/edit'}


@router.post('/settings/applications/admin/{id:int}/reset-client-secret')
async def reset_client_secret(
    _: Annotated[User, web_user()],
    id: Annotated[int, Path()],
):
    client_secret = await OAuth2ApplicationService.reset_client_secret(id)
    return {'client_secret': client_secret.get_secret_value()}


@router.post('/settings/applications/admin/{id:int}/delete')
async def delete_application(
    _: Annotated[User, web_user()],
    id: Annotated[int, Path()],
):
    await OAuth2ApplicationService.delete(id)
    return {'redirect_url': '/settings/applications/admin'}
