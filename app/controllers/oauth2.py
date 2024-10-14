from typing import Annotated

from fastapi import APIRouter, Query

from app.config import APP_URL
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.oauth2_token import (
    OAuth2CodeChallengeMethod,
    OAuth2GrantType,
    OAuth2ResponseMode,
    OAuth2ResponseType,
)
from app.models.db.user import User
from app.models.scope import PUBLIC_SCOPES, Scope
from app.services.oauth2_token_service import OAuth2TokenService

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
        'token_endpoint_auth_methods_supported': ('client_secret_basic', 'client_secret_post'),  # TODO:
        'subject_types_supported': ('public',),
        'id_token_signing_alg_values_supported': ('RS256',),  # TODO:
        'claim_types_supported': ('normal',),
        'claims_supported': ('iss', 'sub', 'aud', 'exp', 'iat', 'preferred_username', 'email'),  # TODO:
    }


@router.get('/oauth2/authorize')
async def authorize(
    _: Annotated[User, web_user()],
    client_id: Annotated[str, Query(min_length=1)],
    redirect_uri: Annotated[str, Query(min_length=1)],
    scope: Annotated[str, Query(min_length=1)],
    code_challenge_method: Annotated[OAuth2CodeChallengeMethod | None, Query()] = None,
    code_challenge: Annotated[str | None, Query(min_length=1)] = None,
    state: Annotated[str | None, Query(min_length=1)] = None,
    response_type: Annotated[OAuth2ResponseType, Query()] = OAuth2ResponseType.code,
    response_mode: Annotated[OAuth2ResponseMode, Query()] = OAuth2ResponseMode.query,
    init: Annotated[bool, Query(include_in_schema=False)] = True,
):
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
        form_data: list[tuple[str, str]] = [
            ('client_id', client_id),
            ('redirect_uri', redirect_uri),
            ('scope', scope),
            ('response_type', response_type.value),
            ('response_mode', response_mode.value),
            ('init', 'False'),
        ]
        if code_challenge_method is not None:
            form_data.append(('code_challenge_method', code_challenge_method.value))
        if code_challenge is not None:
            form_data.append(('code_challenge', code_challenge))
        if state is not None:
            form_data.append(('state', state))
        return render_response(
            'oauth2/authorize.jinja2',
            {'app': auth_result, 'scopes': scopes, 'redirect_uri': redirect_uri, 'form_data': form_data},
        )
