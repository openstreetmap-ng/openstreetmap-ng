from asyncio import TaskGroup
from typing import Annotated

from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from fastapi import APIRouter
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import web_user
from app.lib.locale import INSTALLED_LOCALES_NAMES_MAP
from app.lib.render_response import render_response
from app.limits import (
    ACTIVE_SESSIONS_DISPLAY_LIMIT,
    EMAIL_MIN_LENGTH,
    PASSWORD_MIN_LENGTH,
    URLSAFE_BLACKLIST,
)
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import User
from app.queries.connected_account_query import ConnectedAccountQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.services.auth_service import AuthService

router = APIRouter()


@router.get('/settings')
async def settings(_: Annotated[User, web_user()]):
    return await render_response(
        'settings/index.jinja2',
        {
            'URLSAFE_BLACKLIST': URLSAFE_BLACKLIST,
            'INSTALLED_LOCALES_NAMES_MAP': INSTALLED_LOCALES_NAMES_MAP,
        },
    )


@router.get('/settings/email')
async def settings_email(_: Annotated[User, web_user()]):
    return await render_response(
        'settings/email.jinja2',
        {
            'EMAIL_MIN_LENGTH': EMAIL_MIN_LENGTH,
            'EMAIL_MAX_LENGTH': EMAIL_MAX_LENGTH,
        },
    )


@router.get('/settings/security')
async def settings_security(user: Annotated[User, web_user()]):
    async with TaskGroup() as tg:
        current_t = tg.create_task(AuthService.authenticate_oauth2(None))
        active_t = tg.create_task(
            OAuth2TokenQuery.find_many_authorized_by_user_client_id(
                user_id=user['id'],
                client_id=SYSTEM_APP_WEB_CLIENT_ID,
                limit=ACTIVE_SESSIONS_DISPLAY_LIMIT,
            )
        )

    current_session = current_t.result()
    assert current_session is not None
    active_sessions = active_t.result()

    return await render_response(
        'settings/security.jinja2',
        {
            'current_session_id': current_session['id'],
            'active_sessions': active_sessions,
            'PASSWORD_MIN_LENGTH': PASSWORD_MIN_LENGTH,
        },
    )


@router.get('/settings/connections')
async def settings_connections(user: Annotated[User, web_user()]):
    provider_id_map = await ConnectedAccountQuery.get_providers_by_user(user['id'])
    return await render_response('settings/connections.jinja2', {'provider_id_map': provider_id_map})


@router.get('/preferences{_:path}')
@router.get('/account/edit')
@router.get('/user/{_:str}/account')
async def legacy_settings(_=None):
    return RedirectResponse('/settings', status.HTTP_301_MOVED_PERMANENTLY)
