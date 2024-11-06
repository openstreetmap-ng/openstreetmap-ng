from typing import Annotated

from fastapi import APIRouter, Cookie, Form, Query, Response
from pydantic import SecretStr
from starlette import status

from app.config import APP_URL, GOOGLE_OAUTH_PUBLIC, GOOGLE_OAUTH_SECRET
from app.lib.buffered_random import buffered_rand_urlsafe
from app.lib.openid import parse_openid_token_no_verify
from app.models.auth_provider import AuthProvider, AuthProviderAction
from app.queries.openid_query import OpenIDQuery
from app.services.auth_provider_service import AuthProviderService
from app.utils import HTTP

router = APIRouter(prefix='/oauth2/google')

_REDIRECT_URI = f'{APP_URL}/oauth2/google/callback'


@router.post('/authorize')
async def google_authorize(
    action: Annotated[AuthProviderAction, Form()],
    referer: Annotated[str | None, Form()] = None,
):
    if not GOOGLE_OAUTH_PUBLIC or not GOOGLE_OAUTH_SECRET:
        return Response('Google OAuth credentials are not configured', status.HTTP_503_SERVICE_UNAVAILABLE)
    openid = await OpenIDQuery.discovery('https://accounts.google.com')
    return AuthProviderService.continue_authorize(
        provider=AuthProvider.google,
        action=action,
        referer=referer,
        redirect_uri=openid['authorization_endpoint'],
        redirect_params={
            'client_id': GOOGLE_OAUTH_PUBLIC,
            'redirect_uri': _REDIRECT_URI,
            'nonce': buffered_rand_urlsafe(16),
            'response_type': 'code',
            'scope': 'openid profile email',
            'access_type': 'online',
        },
    )


@router.get('/callback')
async def google_callback(
    code: Annotated[SecretStr, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
    auth_provider_state: Annotated[str, Cookie()],
):
    state_ = AuthProviderService.validate_state(
        provider=AuthProvider.google,
        query_state=state,
        cookie_state=auth_provider_state,
    )

    openid = await OpenIDQuery.discovery('https://accounts.google.com')
    r = await HTTP.post(
        openid['token_endpoint'],
        data={
            'client_id': GOOGLE_OAUTH_PUBLIC,
            'client_secret': GOOGLE_OAUTH_SECRET,
            'redirect_uri': _REDIRECT_URI,
            'grant_type': 'authorization_code',
            'code': code.get_secret_value(),
        },
    )
    r.raise_for_status()
    id_token = SecretStr(r.json()['id_token'])
    payload = parse_openid_token_no_verify(id_token.get_secret_value())
    return await AuthProviderService.continue_callback(
        state=state_,
        uid=payload['sub'],
        name=payload.get('name'),
        email=payload.get('email'),
    )
