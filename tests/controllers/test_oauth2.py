from itertools import product
from urllib.parse import parse_qs, urlsplit

import pytest
from authlib.integrations.httpx_client import AsyncOAuth2Client
from httpx import AsyncClient
from starlette import status

from app.config import APP_URL
from app.lib.buffered_random import buffered_rand_urlsafe
from app.lib.date_utils import utcnow
from app.lib.locale import DEFAULT_LOCALE
from app.lib.xmltodict import XMLToDict
from app.models.db.oauth2_token import OAuth2CodeChallengeMethod, OAuth2ResponseMode, OAuth2TokenEndpointAuthMethod


async def test_openid_configuration(client: AsyncClient):
    r = await client.get('/.well-known/openid-configuration')
    assert r.is_success, r.text

    config = r.json()
    assert config['issuer'] == APP_URL
    assert config['authorization_endpoint'] == f'{APP_URL}/oauth2/authorize'
    assert config['token_endpoint'] == f'{APP_URL}/oauth2/token'


async def test_authorize_invalid_system_app(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id='SystemApp.web',
        scope='',
        redirect_uri='urn:ietf:wg:oauth:2.0:oob',
    )
    authorization_url, _ = auth_client.create_authorization_url('/oauth2/authorize')

    r = await client.post(authorization_url)
    assert r.status_code == status.HTTP_401_UNAUTHORIZED
    assert r.json()['detail'] == 'Invalid client ID'


async def test_authorize_invalid_extra_scopes(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id='testapp-minimal',
        scope='read_prefs',
        redirect_uri='urn:ietf:wg:oauth:2.0:oob',
    )
    authorization_url, _ = auth_client.create_authorization_url('/oauth2/authorize')

    r = await client.post(authorization_url)
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert r.json()['detail'] == 'Invalid authorization scopes'


@pytest.mark.parametrize(
    ('code_challenge_method', 'token_endpoint_auth_method'),
    list(product(OAuth2CodeChallengeMethod, OAuth2TokenEndpointAuthMethod)),
)
async def test_authorize_token_oob(
    client: AsyncClient,
    code_challenge_method: OAuth2CodeChallengeMethod,
    token_endpoint_auth_method: OAuth2TokenEndpointAuthMethod,
):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id='testapp-secret',
        client_secret='testapp.secret',  # noqa: S106
        scope='',
        redirect_uri='urn:ietf:wg:oauth:2.0:oob',
        code_challenge_method=code_challenge_method.value,
        token_endpoint_auth_method=token_endpoint_auth_method.value,
    )
    code_verifier = buffered_rand_urlsafe(48)

    if code_challenge_method == OAuth2CodeChallengeMethod.plain:  # authlib doesn't support plain method
        authorization_url, state = auth_client.create_authorization_url(
            '/oauth2/authorize', code_challenge=code_verifier, code_challenge_method='plain'
        )
    else:
        authorization_url, state = auth_client.create_authorization_url(
            '/oauth2/authorize', code_verifier=code_verifier
        )

    r = await client.post(authorization_url)
    assert r.is_success, r.text

    authorization_code = r.headers['Test-OAuth2-Authorization-Code']
    authorization_code, _, state_response = authorization_code.partition('#')
    assert state == state_response

    data: dict = await auth_client.fetch_token(
        '/oauth2/token',
        grant_type='authorization_code',
        auth=('testapp-secret', 'testapp.secret'),
        code=authorization_code,
        code_verifier=code_verifier,
    )
    assert data['access_token']
    assert data['token_type'] == 'Bearer'
    assert data['scope'] == ''
    assert data['created_at']

    r = await auth_client.get('/api/0.6/user/details.json')
    assert r.is_success, r.text

    user = r.json()['user']
    assert user['display_name'] == 'user1'


@pytest.mark.parametrize('is_fragment', [False, True])
async def test_authorize_token_response_redirect(client: AsyncClient, is_fragment: bool):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id='testapp-secret',
        client_secret='testapp.secret',  # noqa: S106
        scope='',
        redirect_uri='http://localhost/callback',
    )
    authorization_url, state = auth_client.create_authorization_url(
        '/oauth2/authorize', response_mode=OAuth2ResponseMode.fragment if is_fragment else OAuth2ResponseMode.query
    )

    r = await client.post(authorization_url)
    assert r.is_redirect, r.text
    assert r.has_redirect_location, r.text

    parts = urlsplit(r.headers['Location'])
    query = parse_qs(parts.fragment if is_fragment else parts.query)

    authorization_code = query['code'][0]
    state_response = query['state'][0]
    assert state == state_response

    data: dict = await auth_client.fetch_token(
        '/oauth2/token',
        grant_type='authorization_code',
        auth=('testapp-secret', 'testapp.secret'),
        code=authorization_code,
    )
    assert data['access_token']
    assert data['token_type'] == 'Bearer'
    assert data['scope'] == ''
    assert data['created_at']

    r = await auth_client.get('/api/0.6/user/details.json')
    assert r.is_success, r.text

    user = r.json()['user']
    assert user['display_name'] == 'user1'


async def test_authorize_response_form_post(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id='testapp-secret',
        client_secret='testapp.secret',  # noqa: S106
        scope='',
        redirect_uri='http://localhost/callback',
    )
    authorization_url, state = auth_client.create_authorization_url(
        '/oauth2/authorize', response_mode=OAuth2ResponseMode.form_post
    )

    r = await client.post(authorization_url)
    assert r.is_success, r.text
    assert 'action="http://localhost/callback"' in r.text


async def test_authorize_token_introspect_userinfo_revoke_public_app(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id='testapp',
        scope='',
        redirect_uri='urn:ietf:wg:oauth:2.0:oob',
    )
    authorization_url, state = auth_client.create_authorization_url('/oauth2/authorize')

    r = await client.post(authorization_url)
    assert r.is_success, r.text

    authorization_code = r.headers['Test-OAuth2-Authorization-Code']
    authorization_code, _, state_response = authorization_code.partition('#')
    assert state == state_response

    authorization_date = utcnow()
    data: dict = await auth_client.fetch_token(
        '/oauth2/token',
        grant_type='authorization_code',
        code=authorization_code,
    )
    assert data['access_token']
    assert data['token_type'] == 'Bearer'
    assert data['scope'] == ''
    assert data['created_at']
    access_token = data['access_token']

    r = await auth_client.get('/api/0.6/user/details.json')
    assert r.is_success, r.text
    assert r.json()['user']['display_name'] == 'user1'

    r = await auth_client.post('/oauth2/introspect', data={'token': access_token})
    assert r.is_success, r.text
    data = r.json()
    assert data['active'] is True
    assert data['iss'] == APP_URL
    assert data['iat'] >= int(authorization_date.timestamp())
    assert data['client_id'] == 'testapp'
    assert data['scope'] == ''
    assert data['username'] == 'user1'
    assert 'exp' not in data

    r = await auth_client.get('/oauth2/userinfo')
    assert r.is_success, r.text
    data = r.json()
    assert data['username'] == 'user1'
    assert data['picture'].startswith(APP_URL)
    assert data['locale'] == DEFAULT_LOCALE
    r = await auth_client.get(data['picture'])
    r.raise_for_status()

    r = await auth_client.post('/oauth2/revoke', data={'token': access_token})
    assert r.is_success, r.text

    r = await auth_client.get('/api/0.6/user/details.json')
    assert r.status_code == status.HTTP_401_UNAUTHORIZED, r.text
    r = await auth_client.post('/oauth2/introspect', data={'token': access_token})
    assert r.status_code == status.HTTP_401_UNAUTHORIZED, r.text


async def test_access_token_in_form(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id='testapp',
        scope='',
        redirect_uri='urn:ietf:wg:oauth:2.0:oob',
    )
    authorization_url, state = auth_client.create_authorization_url('/oauth2/authorize')

    r = await client.post(authorization_url)
    assert r.is_success, r.text

    authorization_code = r.headers['Test-OAuth2-Authorization-Code']
    authorization_code, _, state_response = authorization_code.partition('#')
    assert state == state_response

    data: dict = await auth_client.fetch_token(
        '/oauth2/token',
        grant_type='authorization_code',
        code=authorization_code,
    )

    client.headers.pop('Authorization')
    # create note
    r = await client.post(
        '/api/0.6/notes',
        params={'lon': 0, 'lat': 0, 'text': test_access_token_in_form.__qualname__},
        data={'access_token': data['access_token']},
    )
    assert r.is_success, r.text
    props: dict = XMLToDict.parse(r.content)['osm']['note']
    comments: list[dict] = props['comments']['comment']
    assert comments[-1]['user'] == 'user1'
