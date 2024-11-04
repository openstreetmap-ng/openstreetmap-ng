from typing import Annotated

from fastapi import APIRouter, Form, Response, UploadFile

from app.lib.auth_context import web_user
from app.lib.standard_feedback import StandardFeedback
from app.limits import USER_DESCRIPTION_MAX_LENGTH
from app.models.db.user import AvatarType, Editor, User
from app.models.types import LocaleCode, PasswordType, ValidatingDisplayNameType
from app.services.auth_service import AuthService
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.user_service import UserService
from app.validators.email import ValidatingEmailType

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
    feedback = StandardFeedback()
    await UserService.update_email(
        feedback,
        new_email=email,
        password=password,
    )
    return feedback.result


@router.post('/settings/password')
async def settings_password(
    _: Annotated[User, web_user()],
    old_password: Annotated[PasswordType, Form()],
    new_password: Annotated[PasswordType, Form()],
    revoke_other_sessions: Annotated[bool, Form()] = False,
):
    feedback = StandardFeedback()
    await UserService.update_password(
        feedback,
        old_password=old_password,
        new_password=new_password,
    )
    if revoke_other_sessions:
        current_session = await AuthService.authenticate_oauth2(None)
        await OAuth2TokenService.revoke_by_client_id('SystemApp.web', skip_ids=(current_session.id,))  # pyright: ignore[reportOptionalMemberAccess]
    return feedback.result


@router.post('/settings/description')
async def settings_description(
    _: Annotated[User, web_user()],
    description: Annotated[str, Form(max_length=USER_DESCRIPTION_MAX_LENGTH)],
):
    await UserService.update_description(description=description)
    return Response()
