from typing import Annotated

from fastapi import APIRouter, Form, Query

from app.lib_cython.auth_context import web_user
from app.lib_cython.legal import get_legal
from app.lib_cython.translation import render
from app.models.auth_provider import AuthProvider
from app.models.db.user import User
from app.models.editor import Editor
from app.models.str import EmptyEmailStr, EmptyPasswordStr, UserNameStr
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService

router = APIRouter(prefix='/user')


@router.get('/display_name_available')
async def display_name_available(
    display_name: Annotated[UserNameStr, Query()],
) -> bool:
    return await UserRepository.check_display_name_available(display_name)


# TODO: http caching
@router.get('/terms')
async def terms(
    locale: Annotated[str, Query(regex=r'^(FR|GB|IT)$')],
) -> str:
    # TODO: fix: Please read the following terms and conditions carefully and click either the 'Accept' or 'Decline' button at the bottom to continue.
    document = get_legal(locale)
    return render('api/web/terms.jinja2', document=document)


# TODO: some system to respond errors, information, etc.
# TODO: captcha
@router.post('/settings')
async def update_settings(
    display_name: Annotated[UserNameStr, Form()],
    new_email: Annotated[EmptyEmailStr, Form()],
    new_password: Annotated[EmptyPasswordStr, Form()],
    auth_provider: Annotated[AuthProvider | None, Form()],
    auth_uid: Annotated[str, Form()],
    editor: Annotated[Editor | None, Form()],
    languages: Annotated[str, Form()],
    _: Annotated[User, web_user()],
) -> None:
    await UserService.update_settings(
        display_name=display_name,
        new_email=new_email,
        new_password=new_password,
        auth_provider=auth_provider,
        auth_uid=auth_uid,
        editor=editor,
        languages=languages,
    )
