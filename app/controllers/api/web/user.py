from typing import Annotated

from fastapi import APIRouter, Form, Query, Request
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import web_user
from app.lib.message_collector import MessageCollector
from app.models.db.user import User
from app.models.str import DisplayNameStr, EmailStr, PasswordStr
from app.repositories.user_repository import UserRepository
from app.services.user_signup_service import UserSignupService

router = APIRouter(prefix='/user')


# TODO: frontend implement
@router.get('/display-name-available')
async def display_name_available(
    display_name: Annotated[DisplayNameStr, Query()],
) -> bool:
    return await UserRepository.check_display_name_available(display_name)


# TODO: captcha
@router.post('/signup')
async def signup(
    request: Request,
    display_name: Annotated[DisplayNameStr, Form()],
    email: Annotated[EmailStr, Form()],
    password: Annotated[PasswordStr, Form()],
):
    collector = MessageCollector()
    token = await UserSignupService.signup(
        collector,
        display_name=display_name,
        email=email,
        password=password,
    )
    request.session['session'] = str(token)
    return collector.result


@router.post('/abort-signup')
async def abort_signup(
    request: Request,
    _: Annotated[User, web_user()],
):
    await UserSignupService.abort_signup()
    request.session.pop('session', None)
    return RedirectResponse('/', status.HTTP_303_SEE_OTHER)


@router.post('/accept-terms')
async def accept_terms(
    _: Annotated[User, web_user()],
):
    await UserSignupService.accept_terms()
    return RedirectResponse('/user/pending-activation', status.HTTP_303_SEE_OTHER)


# @router.post('/settings')
# async def update_settings(
#     display_name: Annotated[DisplayNameStr, Form()],
#     new_email: Annotated[EmptyEmailStr, Form()],
#     new_password: Annotated[EmptyPasswordStr, Form()],
#     auth_provider: Annotated[AuthProvider | None, Form()],
#     auth_uid: Annotated[str, Form()],
#     editor: Annotated[Editor | None, Form()],
#     languages: Annotated[str, Form()],
#     _: Annotated[User, web_user()],
# ) -> None:
#     await UserService.update_settings(
#         display_name=display_name,
#         new_email=new_email,
#         new_password=new_password,
#         auth_provider=auth_provider,
#         auth_uid=auth_uid,
#         editor=editor,
#         languages=languages,
#     )
