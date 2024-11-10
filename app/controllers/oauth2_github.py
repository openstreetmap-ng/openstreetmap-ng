from typing import Annotated

from fastapi import APIRouter, Cookie, Form, Query, Response
from pydantic import SecretStr
from starlette import status

from app.config import GITHUB_OAUTH_PUBLIC, GITHUB_OAUTH_SECRET
from app.models.auth_provider import AuthProvider, AuthProviderAction
from app.services.auth_provider_service import AuthProviderService
from app.utils import HTTP

router = APIRouter(prefix='/oauth2/github')


@router.post('/authorize')
async def github_authorize(
    action: Annotated[AuthProviderAction, Form()],
    referer: Annotated[str | None, Form()] = None,
):
    if not GITHUB_OAUTH_PUBLIC or not GITHUB_OAUTH_SECRET:
        return Response('GitHub OAuth credentials are not configured', status.HTTP_503_SERVICE_UNAVAILABLE)
    return AuthProviderService.continue_authorize(
        provider=AuthProvider.github,
        action=action,
        referer=referer,
        redirect_uri='https://github.com/login/oauth/authorize',
        redirect_params={
            'client_id': GITHUB_OAUTH_PUBLIC,
            'scope': 'read:user user:email',
        },
    )


@router.get('/callback')
async def github_callback(
    code: Annotated[SecretStr, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
    auth_provider_state: Annotated[str, Cookie()],
):
    state_ = AuthProviderService.validate_state(
        provider=AuthProvider.github,
        query_state=state,
        cookie_state=auth_provider_state,
    )

    r = await HTTP.post(
        'https://github.com/login/oauth/access_token',
        headers={'Accept': 'application/json'},
        data={
            'client_id': GITHUB_OAUTH_PUBLIC,
            'client_secret': GITHUB_OAUTH_SECRET,
            'code': code.get_secret_value(),
        },
    )
    r.raise_for_status()
    access_token = SecretStr(r.json()['access_token'])

    r = await HTTP.get(
        'https://api.github.com/user',
        headers={
            'Authorization': f'Bearer {access_token.get_secret_value()}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        },
    )
    r.raise_for_status()
    user = r.json()
    return await AuthProviderService.continue_callback(
        state=state_,
        uid=user['id'],
        name=user.get('login'),
        email=user.get('email'),
    )
