from asyncio import TaskGroup
from typing import Annotated

from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from fastapi import APIRouter
from starlette import status
from starlette.responses import RedirectResponse

from app.config import (
    ACTIVE_SESSIONS_DISPLAY_LIMIT,
    EMAIL_MIN_LENGTH,
    PASSWORD_MIN_LENGTH,
    URLSAFE_BLACKLIST,
)
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import User
from app.queries.connected_account_query import ConnectedAccountQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_totp_query import UserTOTPQuery
from app.services.auth_service import AuthService

router = APIRouter()


@router.get('/settings')
async def settings(_: Annotated[User, web_user()]):
    return await render_response(
        'settings/settings',
        {'URLSAFE_BLACKLIST': URLSAFE_BLACKLIST},
    )


@router.get('/settings/email')
async def settings_email(_: Annotated[User, web_user()]):
    return await render_response(
        'settings/email',
        {
            'EMAIL_MIN_LENGTH': EMAIL_MIN_LENGTH,
            'EMAIL_MAX_LENGTH': EMAIL_MAX_LENGTH,
        },
    )


@router.get('/settings/security')
async def settings_security(user: Annotated[User, web_user()]):
    async with TaskGroup() as tg:
        totp_t = tg.create_task(UserTOTPQuery.find_one_by_user_id(user['id']))
        current_t = tg.create_task(AuthService.authenticate_oauth2(None))
        active_t = tg.create_task(
            OAuth2TokenQuery.find_authorized_by_user_client_id(
                user_id=user['id'],
                client_id=SYSTEM_APP_WEB_CLIENT_ID,
                limit=ACTIVE_SESSIONS_DISPLAY_LIMIT,
            )
        )

    return await render_response(
        'settings/security',
        {
            'has_totp': totp_t.result() is not None,
            'current_session_id': current_t.result()['id'],  # type: ignore
            'active_sessions': active_t.result(),
            'PASSWORD_MIN_LENGTH': PASSWORD_MIN_LENGTH,
        },
    )


@router.get('/settings/connections')
async def settings_connections(_: Annotated[User, web_user()]):
    accounts = await ConnectedAccountQuery.find_by_user(None)
    provider_id_set = {a['provider'] for a in accounts}
    return await render_response(
        'settings/connections', {'provider_id_set': provider_id_set}
    )


@router.get('/preferences{_:path}')
@router.get('/account/edit')
@router.get('/user/{_:str}/account')
async def legacy_settings(_=None):
    return RedirectResponse('/settings', status.HTTP_301_MOVED_PERMANENTLY)
