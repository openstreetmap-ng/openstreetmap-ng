from typing import Annotated

from fastapi import APIRouter, Form, Query, Response
from starlette import status
from starlette.responses import RedirectResponse

from app.config import TEST_ENV
from app.lib.auth_context import web_user
from app.lib.message_collector import MessageCollector
from app.lib.redirect_response import redirect_response
from app.limits import COOKIE_AUTH_MAX_AGE
from app.models.db.user import User
from app.models.str import DisplayNameStr, EmailStr, PasswordStr
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.user_signup_service import UserSignupService

router = APIRouter(prefix='/user')

# TODO: captcha


# TODO: frontend implement
@router.get('/display-name-available')
async def display_name_available(
    display_name: Annotated[DisplayNameStr, Query()],
) -> bool:
    return await UserRepository.check_display_name_available(display_name)


@router.post('/login')
async def login(
    response: Response,
    display_name_or_email: Annotated[str, Form(min_length=1)],
    password: Annotated[PasswordStr, Form()],
    remember: Annotated[bool, Form(default=False)],
):
    collector = MessageCollector()
    token = await UserService.login(
        collector,
        display_name_or_email=display_name_or_email,
        password=password,
    )
    max_age = COOKIE_AUTH_MAX_AGE if remember else None
    response.set_cookie('auth', str(token), max_age, secure=not TEST_ENV, httponly=True, samesite='lax')
    return collector.result


@router.post('/logout')
async def logout(response: Response):
    await AuthService.logout_session()
    response.delete_cookie('auth')
    return redirect_response()


@router.post('/signup')
async def signup(
    response: Response,
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
    response.set_cookie('auth', str(token), None, secure=not TEST_ENV, httponly=True, samesite='lax')
    return collector.result


@router.post('/accept-terms')
async def accept_terms(
    _: Annotated[User, web_user()],
):
    await UserSignupService.accept_terms()
    return RedirectResponse('/user/pending-activation', status.HTTP_303_SEE_OTHER)


@router.post('/abort-signup')
async def abort_signup(
    response: Response,
    _: Annotated[User, web_user()],
):
    await UserSignupService.abort_signup()
    response.delete_cookie('auth')
    return RedirectResponse('/', status.HTTP_303_SEE_OTHER)


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
