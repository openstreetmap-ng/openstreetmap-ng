from httpx import AsyncClient
from pytest import MonkeyPatch

from app.lib import auth_provider
from app.models.proto.auth_provider_pb2 import (
    StartAuthorizeRequest,
    StartAuthorizeResponse,
)


async def test_start_authorize_github(client: AsyncClient, monkeypatch: MonkeyPatch):
    monkeypatch.setattr(auth_provider, 'GITHUB_OAUTH_PUBLIC', 'test-client-id')

    r = await client.post(
        '/rpc/auth_provider.Service/StartAuthorize',
        headers={'Content-Type': 'application/proto'},
        content=StartAuthorizeRequest(
            provider='github',
            action='login',
            referer='/login',
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    StartAuthorizeResponse.FromString(r.content)
    location = r.headers.get('location')
    assert location is not None
    assert location.startswith('https://github.com/login/oauth/authorize?')
    assert 'client_id=test-client-id' in location
    assert 'state=' in location

    set_cookie = r.headers.get('set-cookie')
    assert set_cookie is not None
    assert 'auth_provider_state=' in set_cookie
