from types import SimpleNamespace

from httpx import AsyncClient
from pytest import MonkeyPatch

from app.lib import auth_provider
from app.services.auth_provider_service import AuthProviderService


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


async def test_github_callback_token_exchange_error(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
):
    def fake_validate_state(*, provider: str, query_state: str, cookie_state: str):
        return SimpleNamespace(
            provider=provider, query_state=query_state, cookie_state=cookie_state
        )

    async def fake_post(*args, **kwargs):
        return _FakeResponse({
            'error': 'bad_verification_code',
            'error_description': 'The code passed is incorrect or expired.',
        })

    monkeypatch.setattr(AuthProviderService, 'validate_state', fake_validate_state)
    monkeypatch.setattr(auth_provider.HTTP, 'post', fake_post)

    r = await client.get(
        '/oauth2/github/callback',
        params={'code': 'expired-code', 'state': 'state-hmac'},
        cookies={'auth_provider_state': 'cookie-state'},
    )
    assert r.status_code == 400, r.text
    assert 'incorrect or expired' in r.text
