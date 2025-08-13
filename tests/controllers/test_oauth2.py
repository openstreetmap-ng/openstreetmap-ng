import sys
from itertools import product
from typing import get_args
from urllib.parse import parse_qs, urlsplit

import pytest
from annotated_types import Ge
from authlib.integrations.httpx_client import AsyncOAuth2Client
from httpx import AsyncClient
from pydantic import PositiveInt
from starlette import status

from app.config import APP_URL
from app.lib.date_utils import utcnow
from app.lib.locale import DEFAULT_LOCALE
from app.lib.xmltodict import XMLToDict
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.oauth2_token import (
    OAuth2CodeChallengeMethod,
    OAuth2ResponseMode,
    OAuth2TokenEndpointAuthMethod,
)
from speedup.buffered_rand import buffered_rand_urlsafe
from tests.utils.assert_model import assert_model


async def test_openid_configuration(client: AsyncClient):
    r = await client.get('/.well-known/openid-configuration')
    assert r.is_success, r.text
    config = r.json()

    assert_model(
        config,
        {
            'issuer': APP_URL,
            'authorization_endpoint': f'{APP_URL}/oauth2/authorize',
            'token_endpoint': f'{APP_URL}/oauth2/token',
        },
    )


async def test_authorize_invalid_system_app(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id=SYSTEM_APP_WEB_CLIENT_ID,
        scope='',
        redirect_uri='urn:ietf:wg:oauth:2.0:oob',
    )
    authorization_url, _ = auth_client.create_authorization_url('/oauth2/authorize')

    # Perform authorization
    r = await client.post(authorization_url)
    assert r.status_code == status.HTTP_401_UNAUTHORIZED, r.text
    assert r.json()['detail'] == 'Invalid client id'


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

    # Perform authorization
    r = await client.post(authorization_url)
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.text
    assert r.json()['detail'] == 'Invalid authorization scopes'


@pytest.mark.parametrize(
    ('code_challenge_method', 'token_endpoint_auth_method'),
    list(
        product(
            get_args(OAuth2CodeChallengeMethod), get_args(OAuth2TokenEndpointAuthMethod)
        )
    ),
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
        code_challenge_method=code_challenge_method,
        token_endpoint_auth_method=token_endpoint_auth_method,
    )
    code_verifier = buffered_rand_urlsafe(32)

    if code_challenge_method == 'plain':  # authlib doesn't support plain method
        authorization_url, state = auth_client.create_authorization_url(
            '/oauth2/authorize',
            code_challenge=code_verifier,
            code_challenge_method='plain',
        )
    else:
        authorization_url, state = auth_client.create_authorization_url(
            '/oauth2/authorize', code_verifier=code_verifier
        )

    # Perform authorization
    r = await client.post(authorization_url)
    assert r.is_success, r.text

    authorization_code = r.headers['Test-OAuth2-Authorization-Code']
    authorization_code, _, state_response = authorization_code.partition('#')
    assert state == state_response, 'State must match in authorization response'

    # Exchange token
    data: dict = await auth_client.fetch_token(
        '/oauth2/token',
        grant_type='authorization_code',
        auth=('testapp-secret', 'testapp.secret'),
        code=authorization_code,
        code_verifier=code_verifier,
    )

    # Verify token data
    assert_model(
        data,
        {
            'access_token': str,
            'token_type': 'Bearer',
            'scope': '',
            'created_at': PositiveInt,
        },
    )

    # Verify token can be used for API access
    r = await auth_client.get('/api/0.6/user/details.json')
    assert r.is_success, r.text
    assert_model(r.json()['user'], {'display_name': 'user1'})


@pytest.mark.parametrize('is_fragment', [False, True])
async def test_authorize_response_redirect(client: AsyncClient, is_fragment):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id='testapp-secret',
        client_secret='testapp.secret',  # noqa: S106
        scope='',
        redirect_uri='http://localhost/callback',
    )

    response_mode: OAuth2ResponseMode = 'fragment' if is_fragment else 'query'
    authorization_url, state = auth_client.create_authorization_url(
        '/oauth2/authorize', response_mode=response_mode
    )

    # Perform authorization
    r = await client.post(authorization_url)
    assert r.is_redirect, r.text
    assert r.has_redirect_location, r.text

    # Extract parameters from redirect URL
    parts = urlsplit(r.headers['Location'])
    query = parse_qs(parts.fragment if is_fragment else parts.query)

    authorization_code = query['code'][0]
    state_response = query['state'][0]
    assert state == state_response, 'State parameter must match in response'

    # Exchange token
    data: dict = await auth_client.fetch_token(
        '/oauth2/token',
        grant_type='authorization_code',
        auth=('testapp-secret', 'testapp.secret'),
        code=authorization_code,
    )

    # Verify token data
    assert_model(
        data,
        {
            'access_token': str,
            'token_type': 'Bearer',
            'scope': '',
            'created_at': PositiveInt,
        },
    )

    # Verify token can be used for API access
    r = await auth_client.get('/api/0.6/user/details.json')
    assert r.is_success, r.text
    assert_model(r.json()['user'], {'display_name': 'user1'})


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
    authorization_url, _ = auth_client.create_authorization_url(
        '/oauth2/authorize', response_mode='form_post'
    )

    # Perform authorization
    r = await client.post(authorization_url)
    assert r.is_success, r.text

    # Verify the response contains a form with the expected fields
    assert 'action="http://localhost/callback"' in r.text
    assert 'name="code"' in r.text
    assert 'name="state"' in r.text


@pytest.mark.skipif(
    sys.platform == 'darwin',
    reason='3rd party compatibility issue: https://github.com/photostructure/batch-cluster.js/issues/58',
)
async def test_token_introspection_and_userinfo(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id='testapp',
        scope='',
        redirect_uri='urn:ietf:wg:oauth:2.0:oob',
    )
    authorization_url, state = auth_client.create_authorization_url('/oauth2/authorize')
    authorization_date = utcnow()

    # Perform authorization
    r = await client.post(authorization_url)
    assert r.is_success, r.text

    authorization_code = r.headers['Test-OAuth2-Authorization-Code']
    authorization_code, _, state_response = authorization_code.partition('#')
    assert state == state_response, 'State must match in authorization response'

    # Exchange token
    data: dict = await auth_client.fetch_token(
        '/oauth2/token', grant_type='authorization_code', code=authorization_code
    )
    access_token = data['access_token']

    # Verify token works for API access
    r = await auth_client.get('/api/0.6/user/details.json')
    assert r.is_success, r.text
    assert_model(r.json()['user'], {'display_name': 'user1'})

    # Test token introspection
    r = await auth_client.post('/oauth2/introspect', data={'token': access_token})
    assert r.is_success, r.text
    introspect_data = r.json()

    assert_model(
        introspect_data,
        {
            'active': True,
            'iss': APP_URL,
            'iat': Ge(int(authorization_date.timestamp())),
            'client_id': 'testapp',
            'scope': '',
            'name': 'user1',
        },
    )
    assert 'exp' not in introspect_data, 'No expiration must be set'

    # Test userinfo endpoint
    r = await auth_client.get('/oauth2/userinfo')
    assert r.is_success, r.text
    userinfo_data = r.json()

    assert_model(
        userinfo_data,
        {
            'name': 'user1',
            'picture': str,
            'locale': DEFAULT_LOCALE,
        },
    )

    # Verify picture URL is accessible
    r = await auth_client.get(userinfo_data['picture'])
    assert r.is_success, r.text


async def test_token_revocation(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id='testapp',
        scope='',
        redirect_uri='urn:ietf:wg:oauth:2.0:oob',
    )
    authorization_url, state = auth_client.create_authorization_url('/oauth2/authorize')

    # Perform authorization
    r = await client.post(authorization_url)
    assert r.is_success, r.text

    authorization_code = r.headers['Test-OAuth2-Authorization-Code']
    authorization_code, _, state_response = authorization_code.partition('#')
    assert state == state_response, 'State must match in authorization response'

    # Exchange token
    data: dict = await auth_client.fetch_token(
        '/oauth2/token', grant_type='authorization_code', code=authorization_code
    )
    access_token = data['access_token']

    # Verify token works before revocation
    r = await auth_client.get('/api/0.6/user/details.json')
    assert r.is_success, r.text

    # Revoke token
    r = await auth_client.post('/oauth2/revoke', data={'token': access_token})
    assert r.is_success, r.text

    # Verify token no longer works
    r = await auth_client.get('/api/0.6/user/details.json')
    assert r.status_code == status.HTTP_401_UNAUTHORIZED, r.text

    # Verify introspection also fails
    r = await auth_client.post('/oauth2/introspect', data={'token': access_token})
    assert r.status_code == status.HTTP_401_UNAUTHORIZED, r.text


@pytest.mark.parametrize('valid_scope', [True, False])
async def test_access_token_in_form(client: AsyncClient, valid_scope):
    client.headers['Authorization'] = 'User user1'
    auth_client = AsyncOAuth2Client(
        base_url=client.base_url,
        transport=client._transport,  # noqa: SLF001
        client_id='testapp',
        scope='write_notes' if valid_scope else '',
        redirect_uri='urn:ietf:wg:oauth:2.0:oob',
    )
    authorization_url, state = auth_client.create_authorization_url('/oauth2/authorize')

    # Perform authorization
    r = await client.post(authorization_url)
    assert r.is_success, r.text

    authorization_code = r.headers['Test-OAuth2-Authorization-Code']
    authorization_code, _, state_response = authorization_code.partition('#')
    assert state == state_response, 'State must match in authorization response'

    # Exchange token
    data: dict = await auth_client.fetch_token(
        '/oauth2/token', grant_type='authorization_code', code=authorization_code
    )
    access_token = data['access_token']

    # Remove authorization header to test form-based token
    client.headers.pop('Authorization')

    # Attempt to create a note using the token in form data
    r = await client.post(
        '/api/0.6/notes',
        params={'lon': 0, 'lat': 0, 'text': test_access_token_in_form.__qualname__},
        data={'access_token': access_token},
    )

    if valid_scope:
        # With valid scope, the request should succeed
        assert r.is_success, r.text
        props: dict = XMLToDict.parse(r.content)['osm']['note'][0]  # type: ignore
        assert len(props['comments']['comment']) == 1
        assert_model(
            props['comments']['comment'][0], {'user': 'user1', 'action': 'opened'}
        )
    else:
        # Without valid scope, the request should fail with permission error
        assert r.status_code == status.HTTP_403_FORBIDDEN, r.text
        assert (
            'The request requires higher privileges than authorized (write_notes)'
            in r.text
        )
