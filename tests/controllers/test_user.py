from base64 import urlsafe_b64decode, urlsafe_b64encode
from time import time

import pytest
from httpx import AsyncClient
from re2 import search
from starlette import status

from app.lib.crypto import hmac_bytes
from app.models.proto.auth_provider_pb2 import Identity
from app.models.proto.server_pb2 import AuthProviderVerification
from app.models.proto.settings_connections_types import Provider
from app.models.proto.signup_pb2 import Page as SignupPage
from app.queries.user_query import UserQuery


def _signup_state(html: str):
    match = search(r'data-state="([^"]+)"', html)
    assert match is not None
    return SignupPage.FromString(urlsafe_b64decode(match.group(1) + '=='))


def _signed_auth_provider_verification(*, provider: Provider, name: str, email: str):
    buffer_b64 = urlsafe_b64encode(
        AuthProviderVerification(
            issued_at=int(time()),
            identity=Identity(provider=provider, name=name, email=email),
            uid='provider-user-id',
        ).SerializeToString()
    )
    hmac_b64 = urlsafe_b64encode(hmac_bytes(buffer_b64))
    return f'{buffer_b64.decode()}.{hmac_b64.decode()}'


@pytest.mark.parametrize('path', ['', '/test', '/test?abc=def'])
async def test_user_permalink(client: AsyncClient, path):
    client.headers['Authorization'] = 'User user1'
    user_id = (await UserQuery.find_by_display_name('user1'))['id']  # type: ignore

    # Test that user id permalink redirects to username permalink
    r = await client.get(f'/user-id/{user_id}{path}', follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == f'/user/user1{path}'


async def test_user_permalink_not_found(client: AsyncClient):
    r = await client.get('/user-id/0', follow_redirects=False)
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text


async def test_signup_redirect_when_authenticated(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.get('/signup', follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == '/'


async def test_signup_prefills_auth_provider_verification(client: AsyncClient):
    r = await client.get(
        '/signup',
        cookies={
            'auth_provider_verification': _signed_auth_provider_verification(
                provider='github',
                name='GitHub User',
                email='github@example.com',
            )
        },
    )
    assert r.is_success, r.text

    state = _signup_state(r.text)
    assert state.verification.provider == Identity(provider='github').provider
    assert state.verification.name == 'GitHub User'
    assert state.verification.email == 'github@example.com'


@pytest.mark.parametrize(
    ('old_path', 'new_path'),
    [
        ('/user/new', '/signup'),
        ('/user/forgot-password', '/reset-password'),
        ('/user/reset-password?token=abc123', '/reset-password?token=abc123'),
    ],
)
async def test_legacy_redirects(client: AsyncClient, old_path, new_path):
    r = await client.get(old_path, follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == new_path
