from typing import Annotated

from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from fastapi import APIRouter
from sqlalchemy.orm import joinedload

from app.lib.auth_context import web_user
from app.lib.locale import INSTALLED_LOCALES_NAMES_MAP
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.limits import (
    ACTIVE_SESSIONS_DISPLAY_LIMIT,
    EMAIL_MIN_LENGTH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    URLSAFE_BLACKLIST,
)
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.oauth2_token import OAuth2Token
from app.models.db.user import User
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.services.auth_service import AuthService

router = APIRouter()


@router.get('/settings')
async def settings(_: Annotated[User, web_user()]):
    return render_response(
        'settings/index.jinja2',
        {
            'URLSAFE_BLACKLIST': URLSAFE_BLACKLIST,
            'INSTALLED_LOCALES_NAMES_MAP': INSTALLED_LOCALES_NAMES_MAP,
        },
    )


@router.get('/settings/email')
async def settings_email(_: Annotated[User, web_user()]):
    return render_response(
        'settings/email.jinja2',
        {
            'EMAIL_MIN_LENGTH': EMAIL_MIN_LENGTH,
            'EMAIL_MAX_LENGTH': EMAIL_MAX_LENGTH,
        },
    )


@router.get('/settings/security')
async def settings_security(user: Annotated[User, web_user()]):
    current_session = await AuthService.authenticate_oauth2(None)
    active_sessions = await OAuth2TokenQuery.find_many_authorized_by_user_client_id(
        user_id=user.id,
        client_id='SystemApp.web',
        limit=ACTIVE_SESSIONS_DISPLAY_LIMIT,
    )
    return render_response(
        'settings/security.jinja2',
        {
            'current_session_id': current_session.id,  # pyright: ignore[reportOptionalMemberAccess]
            'active_sessions': active_sessions,
            'PASSWORD_MIN_LENGTH': PASSWORD_MIN_LENGTH,
            'PASSWORD_MAX_LENGTH': PASSWORD_MAX_LENGTH,
        },
    )


@router.get('/settings/applications')
async def applications(
    user: Annotated[User, web_user()],
):
    with options_context(
        joinedload(OAuth2Token.application)  #
        .joinedload(OAuth2Application.user)
        .load_only(User.display_name),
    ):
        tokens = await OAuth2TokenQuery.find_unique_per_app_by_user_id(user.id)
    return render_response(
        'settings/applications.jinja2',
        {
            'tokens': tokens,
        },
    )
