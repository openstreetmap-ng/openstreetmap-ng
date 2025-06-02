from typing import Annotated

from fastapi import APIRouter, Cookie, Form, Query, Response
from pydantic import SecretStr
from starlette import status

from app.config import APP_URL, FACEBOOK_OAUTH_PUBLIC, FACEBOOK_OAUTH_SECRET
from app.models.db.connected_account import AuthProviderAction
from app.services.auth_provider_service import AuthProviderService
from app.utils import HTTP

router = APIRouter(prefix='/oauth2/facebook')

_REDIRECT_URI = f'{APP_URL.replace("127.0.0.1", "localhost")}/oauth2/facebook/callback'


@router.post('/authorize')
async def facebook_authorize(
    action: Annotated[AuthProviderAction, Form()],
    referer: Annotated[str | None, Form()] = None,
):
    if not FACEBOOK_OAUTH_PUBLIC:
        return Response(
            'Facebook OAuth credentials are not configured',
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return AuthProviderService.continue_authorize(
        provider='facebook',
        action=action,
        referer=referer,
        redirect_uri='https://www.facebook.com/v22.0/dialog/oauth',
        redirect_params={
            'client_id': FACEBOOK_OAUTH_PUBLIC,
            'redirect_uri': _REDIRECT_URI,
            'response_type': 'code',
            'scope': 'email public_profile',
        },
    )


@router.get('/callback')
async def facebook_callback(
    code: Annotated[SecretStr, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
    auth_provider_state: Annotated[str, Cookie()],
):
    state_ = AuthProviderService.validate_state(
        provider='facebook',
        query_state=state,
        cookie_state=auth_provider_state,
    )

    r = await HTTP.get(
        'https://graph.facebook.com/v22.0/oauth/access_token',
        params={
            'client_id': FACEBOOK_OAUTH_PUBLIC,
            'client_secret': FACEBOOK_OAUTH_SECRET.get_secret_value(),
            'redirect_uri': _REDIRECT_URI,
            'code': code.get_secret_value(),
        },
    )
    r.raise_for_status()
    access_token = SecretStr(r.json()['access_token'])

    r = await HTTP.get(
        'https://graph.facebook.com/v22.0/me',
        params={
            'access_token': access_token.get_secret_value(),
            'fields': 'id,name,email',
        },
    )
    r.raise_for_status()
    userinfo = r.json()
    return await AuthProviderService.continue_callback(
        state=state_,
        uid=userinfo['id'],
        name=userinfo.get('name'),
        email=userinfo.get('email'),
    )
