from typing import Any, TypedDict, assert_never

import cython
from fastapi import HTTPException
from httpx import Response
from pydantic import SecretStr
from starlette import status

from app.config import (
    APP_URL,
    FACEBOOK_OAUTH_PUBLIC,
    FACEBOOK_OAUTH_SECRET,
    GITHUB_OAUTH_PUBLIC,
    GITHUB_OAUTH_SECRET,
    GOOGLE_OAUTH_PUBLIC,
    GOOGLE_OAUTH_SECRET,
    MICROSOFT_OAUTH_PUBLIC,
    WIKIMEDIA_OAUTH_PUBLIC,
    WIKIMEDIA_OAUTH_SECRET,
)
from app.lib.openid import parse_openid_token_no_verify
from app.models.proto.settings_connections_types import Provider
from app.queries.openid_query import OpenIDQuery
from app.utils import HTTP
from speedup import buffered_rand_urlsafe

_GOOGLE_REDIRECT_URI = f'{APP_URL}/oauth2/google/callback'
_FACEBOOK_REDIRECT_URI = f'{APP_URL}/oauth2/facebook/callback'


class AuthProviderIdentity(TypedDict):
    uid: str
    name: str | None
    email: str | None


@cython.cfunc
def _require_configured(public: str, service_name: str):
    if public:
        return public
    raise HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        f'{service_name} OAuth credentials are not configured',
    )


@cython.cfunc
def _require_oauth_value(
    service_name: str,
    response: Response,
    field: str,
):
    payload: dict[str, Any] = response.json()
    value = payload.get(field)
    if isinstance(value, str) and value:
        return SecretStr(value)

    error_detail = payload.get('error_description') or payload.get('error')
    detail = (
        f'{service_name} OAuth token exchange failed: {error_detail}'
        if isinstance(error_detail, str) and error_detail
        else f'{service_name} OAuth token exchange failed'
    )
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail)


async def get_authorize_redirect(
    provider: Provider,
):
    if provider == 'google':
        public = _require_configured(GOOGLE_OAUTH_PUBLIC, 'Google')
        openid = await OpenIDQuery.discovery('https://accounts.google.com')
        return openid['authorization_endpoint'], {
            'client_id': public,
            'redirect_uri': _GOOGLE_REDIRECT_URI,
            'nonce': buffered_rand_urlsafe(16),
            'response_type': 'code',
            'scope': 'openid profile email',
            'access_type': 'online',
        }
    if provider == 'facebook':
        public = _require_configured(FACEBOOK_OAUTH_PUBLIC, 'Facebook')
        return 'https://www.facebook.com/v22.0/dialog/oauth', {
            'client_id': public,
            'redirect_uri': _FACEBOOK_REDIRECT_URI,
            'response_type': 'code',
            'scope': 'email public_profile',
        }
    if provider == 'microsoft':
        public = _require_configured(MICROSOFT_OAUTH_PUBLIC, 'Microsoft')
        openid = await OpenIDQuery.discovery(
            'https://login.microsoftonline.com/common/v2.0'
        )
        return openid['authorization_endpoint'], {
            'client_id': public,
            'nonce': buffered_rand_urlsafe(16),
            'response_type': 'id_token',
            'response_mode': 'fragment',
            'scope': 'openid profile email',
        }
    if provider == 'github':
        public = _require_configured(GITHUB_OAUTH_PUBLIC, 'GitHub')
        return 'https://github.com/login/oauth/authorize', {
            'client_id': public,
            'scope': 'read:user user:email',
        }
    if provider == 'wikimedia':
        public = _require_configured(WIKIMEDIA_OAUTH_PUBLIC, 'Wikimedia')
        return 'https://meta.wikimedia.org/w/rest.php/oauth2/authorize', {
            'client_id': public,
            'response_type': 'code',
        }
    assert_never(provider)


async def resolve_code_identity(
    *,
    provider: Provider,
    code: SecretStr,
) -> AuthProviderIdentity:
    if provider == 'microsoft':
        raise NotImplementedError(f'Use resolve_id_token_identity for {provider=!r}')

    code_ = code.get_secret_value()

    if provider == 'google':
        openid = await OpenIDQuery.discovery('https://accounts.google.com')
        r = await HTTP.post(
            openid['token_endpoint'],
            data={
                'client_id': GOOGLE_OAUTH_PUBLIC,
                'client_secret': GOOGLE_OAUTH_SECRET.get_secret_value(),
                'redirect_uri': _GOOGLE_REDIRECT_URI,
                'grant_type': 'authorization_code',
                'code': code_,
            },
        )
        r.raise_for_status()
        id_token = _require_oauth_value('Google', r, 'id_token')
        payload = parse_openid_token_no_verify(id_token.get_secret_value())
        return {
            'uid': payload['sub'],
            'name': payload.get('name'),
            'email': payload.get('email'),
        }
    if provider == 'facebook':
        r = await HTTP.get(
            'https://graph.facebook.com/v22.0/oauth/access_token',
            params={
                'client_id': FACEBOOK_OAUTH_PUBLIC,
                'client_secret': FACEBOOK_OAUTH_SECRET.get_secret_value(),
                'redirect_uri': _FACEBOOK_REDIRECT_URI,
                'code': code_,
            },
        )
        r.raise_for_status()
        access_token = _require_oauth_value('Facebook', r, 'access_token')

        r = await HTTP.get(
            'https://graph.facebook.com/v22.0/me',
            params={
                'access_token': access_token.get_secret_value(),
                'fields': 'id,name,email',
            },
        )
        r.raise_for_status()
        userinfo = r.json()
        return {
            'uid': str(userinfo['id']),
            'name': userinfo.get('name'),
            'email': userinfo.get('email'),
        }
    if provider == 'github':
        r = await HTTP.post(
            'https://github.com/login/oauth/access_token',
            headers={'Accept': 'application/json'},
            data={
                'client_id': GITHUB_OAUTH_PUBLIC,
                'client_secret': GITHUB_OAUTH_SECRET.get_secret_value(),
                'code': code_,
            },
        )
        r.raise_for_status()
        access_token = _require_oauth_value('GitHub', r, 'access_token')

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
        return {
            'uid': str(user['id']),
            'name': user.get('login'),
            'email': user.get('email'),
        }
    if provider == 'wikimedia':
        r = await HTTP.post(
            'https://meta.wikimedia.org/w/rest.php/oauth2/access_token',
            data={
                'client_id': WIKIMEDIA_OAUTH_PUBLIC,
                'client_secret': WIKIMEDIA_OAUTH_SECRET.get_secret_value(),
                'grant_type': 'authorization_code',
                'code': code_,
            },
        )
        r.raise_for_status()
        access_token = _require_oauth_value('Wikimedia', r, 'access_token')

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
        return {
            'uid': str(userinfo['id']),
            'name': userinfo.get('name'),
            'email': userinfo.get('email'),
        }
    assert_never(provider)


def resolve_id_token_identity(
    *,
    provider: Provider,
    id_token: SecretStr,
) -> AuthProviderIdentity:
    if provider != 'microsoft':
        raise NotImplementedError(f'Use resolve_code_identity for {provider=!r}')

    payload = parse_openid_token_no_verify(id_token.get_secret_value())
    return {
        'uid': payload['sub'],
        'name': payload.get('name'),
        'email': payload.get('email'),
    }
