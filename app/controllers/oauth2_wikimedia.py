from typing import Annotated

from fastapi import APIRouter, Cookie, Form, Query, Response
from pydantic import SecretStr
from starlette import status

from app.config import WIKIMEDIA_OAUTH_PUBLIC, WIKIMEDIA_OAUTH_SECRET
from app.models.auth_provider import AuthProvider, AuthProviderAction
from app.services.auth_provider_service import AuthProviderService
from app.utils import HTTP

router = APIRouter(prefix='/oauth2/wikimedia')


@router.post('/authorize')
async def wikimedia_authorize(
    action: Annotated[AuthProviderAction, Form()],
    referer: Annotated[str | None, Form()] = None,
):
    if not WIKIMEDIA_OAUTH_PUBLIC or not WIKIMEDIA_OAUTH_SECRET:
        return Response('Wikimedia OAuth credentials are not configured', status.HTTP_503_SERVICE_UNAVAILABLE)
    return AuthProviderService.continue_authorize(
        provider=AuthProvider.wikimedia,
        action=action,
        referer=referer,
        redirect_uri='https://meta.wikimedia.org/w/rest.php/oauth2/authorize',
        redirect_params={
            'client_id': WIKIMEDIA_OAUTH_PUBLIC,
            'response_type': 'code',
        },
    )


@router.get('/callback')
async def wikimedia_callback(
    code: Annotated[SecretStr, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
    auth_provider_state: Annotated[str, Cookie()],
):
    state_ = AuthProviderService.validate_state(
        provider=AuthProvider.wikimedia,
        query_state=state,
        cookie_state=auth_provider_state,
    )

    r = await HTTP.post(
        'https://meta.wikimedia.org/w/rest.php/oauth2/access_token',
        data={
            'client_id': WIKIMEDIA_OAUTH_PUBLIC,
            'client_secret': WIKIMEDIA_OAUTH_SECRET,
            'grant_type': 'authorization_code',
            'code': code.get_secret_value(),
        },
    )
    r.raise_for_status()
    access_token = SecretStr(r.json()['access_token'])

    r = await HTTP.get(
        'https://meta.wikimedia.org/w/api.php',
        headers={'Authorization': f'Bearer {access_token.get_secret_value()}'},
        params={
            'action': 'query',
            'meta': 'userinfo',
            'uiprop': 'email',
            'format': 'json',
        },
    )
    r.raise_for_status()
    userinfo = r.json()['query']['userinfo']
    return await AuthProviderService.continue_callback(
        state=state_,
        uid=userinfo['id'],
        name=userinfo.get('name'),
        email=userinfo.get('email'),
    )
