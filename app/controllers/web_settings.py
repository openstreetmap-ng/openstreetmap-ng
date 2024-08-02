from typing import Annotated

from fastapi import APIRouter, Form, Response, UploadFile

from app.lib.auth_context import web_user
from app.lib.message_collector import MessageCollector
from app.models.db.user import AvatarType, Editor, User
from app.models.types import (
    LocaleCode,
    PasswordType,
    ValidatingDisplayNameType,
    ValidatingEmailType,
    ValidatingPasswordType,
)
from app.services.auth_service import AuthService
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
    avatar_file: Annotated[UploadFile | None, Form()] = None,
):
    avatar_url = await UserService.update_avatar(avatar_type, avatar_file)
    return {'avatar_url': avatar_url}


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
