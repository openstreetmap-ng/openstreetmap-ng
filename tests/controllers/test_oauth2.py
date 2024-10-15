from authlib.integrations.httpx_client import AsyncOAuth2Client
from httpx import ASGITransport, AsyncClient

from app.config import APP_URL
from app.lib.buffered_random import buffered_rand_urlsafe


async def test_openid_configuration(client: AsyncClient):
    r = await client.get('/.well-known/openid-configuration')
    assert r.is_success, r.text

    config = r.json()
    assert config['issuer'] == APP_URL
    assert config['authorization_endpoint'] == f'{APP_URL}/oauth2/authorize'
    assert config['token_endpoint'] == f'{APP_URL}/oauth2/token'


# TODO: test:
# client_secret_basic
# client_secret_post
# TODO: ASGITransport
async def test_authorize_token_oob(client: AsyncClient, transport: ASGITransport):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id='testapp',
        client_secret='testapp.secret',  # noqa: S106
        scope='',
        redirect_uri='urn:ietf:wg:oauth:2.0:oob',
        code_challenge_method='S256',
    )
    code_verifier = buffered_rand_urlsafe(48)
    authorization_url, state = auth_client.create_authorization_url('/oauth2/authorize', code_verifier=code_verifier)

    r = await client.post(authorization_url)
    assert r.is_success, r.text

    authorization_code = r.headers['Test-OAuth2-Authorization-Code']
    authorization_code, _, state_response = authorization_code.partition('#')
    assert state == state_response
