from base64 import b64decode
from typing import Annotated

from fastapi import APIRouter, Form, Header, Query, Request
from starlette import status
from starlette.responses import RedirectResponse

from app.config import APP_URL, TEST_ENV
from app.lib.auth_context import web_user
from app.lib.exceptions_context import raise_for
from app.lib.render_response import render_response
from app.limits import OAUTH2_CODE_CHALLENGE_MAX_LENGTH, OAUTH_APP_URI_MAX_LENGTH
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.oauth2_token import (
    OAuth2CodeChallengeMethod,
    OAuth2GrantType,
    OAuth2ResponseMode,
    OAuth2ResponseType,
    OAuth2TokenEndpointAuthMethod,
    OAuth2TokenOOB,
)
from app.models.db.user import User
from app.models.scope import PUBLIC_SCOPES, Scope
from app.services.oauth2_token_service import OAuth2TokenService
from app.utils import extend_query_params

router = APIRouter()


@router.get('/.well-known/openid-configuration')
async def openid_configuration():
    return {
        'issuer': APP_URL,
        'authorization_endpoint': f'{APP_URL}/oauth2/authorize',
        'token_endpoint': f'{APP_URL}/oauth2/token',
        'revocation_endpoint': f'{APP_URL}/oauth2/revoke',
        'introspection_endpoint': f'{APP_URL}/oauth2/introspect',
        'userinfo_endpoint': f'{APP_URL}/oauth2/userinfo',
        'jwks_uri': f'{APP_URL}/oauth2/discovery/keys',
        'scopes_supported': PUBLIC_SCOPES,
        'response_types_supported': tuple(OAuth2ResponseType),
        'response_modes_supported': tuple(OAuth2ResponseMode),
        'grant_types_supported': tuple(OAuth2GrantType),
        'code_challenge_methods_supported': tuple(OAuth2CodeChallengeMethod),
        'token_endpoint_auth_methods_supported': tuple(OAuth2TokenEndpointAuthMethod),
        'subject_types_supported': ('public',),
        'id_token_signing_alg_values_supported': ('RS256',),  # TODO:
        'claim_types_supported': ('normal',),
        'claims_supported': ('iss', 'sub', 'aud', 'exp', 'iat', 'preferred_username', 'email'),  # TODO:
    }


@router.get('/oauth2/authorize')
@router.post('/oauth2/authorize')
async def authorize(
    request: Request,
    _: Annotated[User, web_user()],
    client_id: Annotated[str, Query(min_length=1)],
    redirect_uri: Annotated[str, Query(min_length=1, max_length=OAUTH_APP_URI_MAX_LENGTH)],
    response_type: Annotated[OAuth2ResponseType, Query()],
    response_mode: Annotated[OAuth2ResponseMode, Query()] = OAuth2ResponseMode.query,
    scope: Annotated[str, Query()] = '',
    code_challenge_method: Annotated[OAuth2CodeChallengeMethod | None, Query()] = None,
    code_challenge: Annotated[str | None, Query(min_length=1, max_length=OAUTH2_CODE_CHALLENGE_MAX_LENGTH)] = None,
    state: Annotated[str | None, Query(min_length=1)] = None,
):
    if response_type != OAuth2ResponseType.code:
        raise NotImplementedError(f'Unsupported response type {response_type!r}')

    init = request.method == 'GET'
    scopes = Scope.from_str(scope)
    auth_result = await OAuth2TokenService.authorize(
        init=init,
        client_id=client_id,
        redirect_uri=redirect_uri,
        scopes=scopes,
        code_challenge_method=code_challenge_method,
        code_challenge=code_challenge,
        state=state,
    )

    if isinstance(auth_result, OAuth2Application):
        return render_response(
            'oauth2/authorize.jinja2',
            {'app': auth_result, 'scopes': scopes, 'redirect_uri': redirect_uri},
        )
    if isinstance(auth_result, OAuth2TokenOOB):
        authorization_code = auth_result.authorization_code
        if state is not None:
            authorization_code += f'#{state}'
        response = render_response(
            'oauth2/oob.jinja2',
            {'authorization_code': authorization_code},
        )
        if TEST_ENV:
            response.headers['Test-OAuth2-Authorization-Code'] = authorization_code
        return response
    if response_mode in (OAuth2ResponseMode.query, OAuth2ResponseMode.fragment):
        is_fragment = response_mode == OAuth2ResponseMode.fragment
        final_uri = extend_query_params(redirect_uri, auth_result, fragment=is_fragment)
        return RedirectResponse(final_uri, status.HTTP_303_SEE_OTHER)
    if response_mode == OAuth2ResponseMode.form_post:
        return render_response(
            'oauth2/response_form_post.jinja2',
            {'redirect_uri': redirect_uri, 'auth_result': auth_result},
        )
    raise NotImplementedError(f'Unsupported response mode {response_mode!r}')


@router.post('/oauth2/token')
async def token(
    grant_type: Annotated[OAuth2GrantType, Form()],
    redirect_uri: Annotated[str, Form(min_length=1, max_length=OAUTH_APP_URI_MAX_LENGTH)],
    code: Annotated[str, Form(min_length=1)],
    code_verifier: Annotated[str | None, Form(min_length=1, max_length=OAUTH2_CODE_CHALLENGE_MAX_LENGTH)] = None,
    client_id: Annotated[str | None, Form(min_length=1)] = None,
    client_secret: Annotated[str | None, Form(min_length=1)] = None,
    authorization: Annotated[str | None, Header(min_length=1)] = None,
):
    if grant_type != OAuth2GrantType.authorization_code:
        raise NotImplementedError(f'Unsupported grant type {grant_type!r}')
    if client_id is None and client_secret is None and authorization is not None:
        scheme, _, param = authorization.partition(' ')
        if scheme.casefold() == 'basic':
            client_id, _, client_secret = b64decode(param).decode().partition(':')
    if not client_id:
        raise_for().oauth_bad_client_id()
    if not client_secret:
        raise_for().oauth_bad_client_secret()

    return await OAuth2TokenService.token(
        authorization_code=code,
        verifier=code_verifier,
        redirect_uri=redirect_uri,
    )
