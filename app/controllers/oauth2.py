from asyncio import TaskGroup
from base64 import b64decode
from typing import Annotated, get_args

from fastapi import APIRouter, Form, Header, Query, Request, Response
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.config import APP_URL, ENV, OAUTH_CODE_CHALLENGE_MAX_LENGTH
from app.lib.auth_context import api_user, web_user
from app.lib.exceptions_context import raise_for
from app.lib.render_response import render_response
from app.models.db.oauth2_token import (
    OAuth2CodeChallengeMethod,
    OAuth2GrantType,
    OAuth2ResponseMode,
    OAuth2ResponseType,
    OAuth2TokenEndpointAuthMethod,
    OAuth2TokenOOB,
)
from app.models.db.user import User, user_avatar_url
from app.models.scope import PUBLIC_SCOPES, scope_from_str
from app.models.types import ClientId, Uri
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.openid_query import OpenIDDiscovery
from app.queries.user_query import UserQuery
from app.services.oauth2_token_service import OAuth2TokenService
from app.utils import extend_query_params

router = APIRouter()

_SCOPES_SUPPORTED: list[str] = list(PUBLIC_SCOPES)
_RESPONSE_TYPES_SUPPORTED = list(get_args(OAuth2ResponseType))
_RESPONSE_MODES_SUPPORTED = list(get_args(OAuth2ResponseMode))
_GRANT_TYPES_SUPPORTED = list(get_args(OAuth2GrantType))
_CODE_CHALLENGE_METHODS_SUPPORTED = list(get_args(OAuth2CodeChallengeMethod))
_TOKEN_ENDPOINT_AUTH_METHODS_SUPPORTED = list(get_args(OAuth2TokenEndpointAuthMethod))


@router.get('/.well-known/openid-configuration')
async def openid_configuration() -> OpenIDDiscovery:
    return {
        'issuer': APP_URL,
        'authorization_endpoint': f'{APP_URL}/oauth2/authorize',
        'token_endpoint': f'{APP_URL}/oauth2/token',
        'revocation_endpoint': f'{APP_URL}/oauth2/revoke',
        'introspection_endpoint': f'{APP_URL}/oauth2/introspect',
        'userinfo_endpoint': f'{APP_URL}/oauth2/userinfo',
        'jwks_uri': f'{APP_URL}/oauth2/discovery/keys',  # TODO:
        'scopes_supported': _SCOPES_SUPPORTED,
        'response_types_supported': _RESPONSE_TYPES_SUPPORTED,
        'response_modes_supported': _RESPONSE_MODES_SUPPORTED,
        'grant_types_supported': _GRANT_TYPES_SUPPORTED,
        'code_challenge_methods_supported': _CODE_CHALLENGE_METHODS_SUPPORTED,
        'token_endpoint_auth_methods_supported': _TOKEN_ENDPOINT_AUTH_METHODS_SUPPORTED,
        'subject_types_supported': ['public'],
        'id_token_signing_alg_values_supported': ['RS256'],  # TODO:
        'claim_types_supported': ['normal'],
        'claims_supported': [
            'iss',
            'sub',
            'aud',
            'exp',
            'iat',
            'preferred_username',
            'email',
        ],  # TODO:
    }


@router.get('/oauth2/authorize')
@router.post('/oauth2/authorize')
async def authorize(
    request: Request,
    _: Annotated[User, web_user()],
    client_id: Annotated[ClientId, Query(min_length=1)],
    redirect_uri: Annotated[Uri, Query(min_length=1)],
    response_type: Annotated[OAuth2ResponseType, Query()],
    response_mode: Annotated[OAuth2ResponseMode, Query()] = 'query',
    scope: Annotated[str, Query()] = '',
    code_challenge_method: Annotated[OAuth2CodeChallengeMethod | None, Query()] = None,
    code_challenge: Annotated[
        str | None, Query(min_length=1, max_length=OAUTH_CODE_CHALLENGE_MAX_LENGTH)
    ] = None,
    state: Annotated[str | None, Query(min_length=1)] = None,
):
    if response_type != 'code':
        raise NotImplementedError(f'Unsupported response type {response_type!r}')

    scopes = scope_from_str(scope)
    auth_result = await OAuth2TokenService.authorize(
        init=request.method == 'GET',
        client_id=client_id,
        redirect_uri=redirect_uri,
        scopes=scopes,
        code_challenge_method=code_challenge_method,
        code_challenge=code_challenge,
        state=state,
    )

    if isinstance(auth_result, OAuth2TokenOOB):
        authorization_code = str(auth_result)
        response = await render_response(
            'oauth2/oob',
            {'authorization_code': authorization_code},
        )
        if ENV == 'dev':
            response.headers['Test-OAuth2-Authorization-Code'] = authorization_code
        return response

    if 'redirect_uris' in auth_result:  # is OAuth2Application
        await UserQuery.resolve_users([auth_result])
        return await render_response(
            'oauth2/authorize',
            {'app': auth_result, 'scopes': scopes, 'redirect_uri': redirect_uri},
        )

    if response_mode in {'query', 'fragment'}:
        is_fragment = response_mode == 'fragment'
        final_uri = extend_query_params(redirect_uri, auth_result, fragment=is_fragment)
        return RedirectResponse(final_uri, status.HTTP_303_SEE_OTHER)

    if response_mode == 'form_post':
        return await render_response(
            'oauth2/response-form-post',
            {'redirect_uri': redirect_uri, 'auth_result': auth_result},
        )

    raise NotImplementedError(f'Unsupported response mode {response_mode!r}')


@router.post('/oauth2/token')
async def post_token(
    grant_type: Annotated[OAuth2GrantType, Form()],
    redirect_uri: Annotated[Uri, Form(min_length=1)],
    code: Annotated[str, Form(min_length=1)],
    code_verifier: Annotated[
        str | None, Form(min_length=1, max_length=OAUTH_CODE_CHALLENGE_MAX_LENGTH)
    ] = None,
    client_id: Annotated[ClientId | None, Form(min_length=1)] = None,
    client_secret: Annotated[SecretStr | None, Form(min_length=1)] = None,
    authorization: Annotated[str | None, Header(min_length=1)] = None,
):
    if grant_type != 'authorization_code':
        raise NotImplementedError(f'Unsupported grant type {grant_type!r}')

    if client_id is None and client_secret is None and authorization is not None:
        scheme, _, param = authorization.partition(' ')
        if scheme.casefold() == 'basic':
            client_id, _, client_secret_ = b64decode(param).decode().partition(':')  # type: ignore
            client_secret = SecretStr(client_secret_) if client_secret_ else None
            del client_secret_
        del param
    del authorization

    if client_id is None:
        raise_for.oauth_bad_client_id()

    return await OAuth2TokenService.token(
        client_id=client_id,
        client_secret=client_secret,
        authorization_code=code,
        verifier=code_verifier,
        redirect_uri=redirect_uri,
    )


@router.post('/oauth2/revoke')
async def revoke(token: Annotated[SecretStr, Form(min_length=1)]):
    await OAuth2TokenService.revoke_by_access_token(token)
    return Response(None, status.HTTP_204_NO_CONTENT)


# Generally this endpoint should not be publicly accessible.
# In this case it's fine, since we don't expose any sensitive information.
@router.post('/oauth2/introspect')
async def introspect(token: Annotated[SecretStr, Form(min_length=1)]):
    token_ = await OAuth2TokenQuery.find_one_authorized_by_token(token)
    if token_ is None:
        raise_for.oauth_bad_user_token()

    async with TaskGroup() as tg:
        items = [token_]
        tg.create_task(UserQuery.resolve_users(items))
        tg.create_task(OAuth2ApplicationQuery.resolve_applications(items))

    return {
        'active': True,
        'iss': APP_URL,
        'iat': int(token_['authorized_at'].timestamp()),  # type: ignore
        'client_id': token_['application']['client_id'],  # pyright: ignore [reportTypedDictNotRequiredAccess]
        'scope': ' '.join(token_['scopes']),
        'sub': str(token_['user_id']),
        'name': token_['user']['display_name'],  # pyright: ignore [reportTypedDictNotRequiredAccess]
    }


@router.get('/oauth2/userinfo')
@router.post('/oauth2/userinfo')
async def userinfo(user: Annotated[User, api_user()]):
    return {
        # TODO: compare fields with osm ruby
        'sub': str(user['id']),
        'name': user['display_name'],
        'picture': f'{APP_URL}{user_avatar_url(user)}',
        'locale': user['language'],
    }
