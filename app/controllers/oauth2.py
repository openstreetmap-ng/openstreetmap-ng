from fastapi import APIRouter

from app.config import APP_URL
from app.models.db.oauth2_token import (
    OAuth2CodeChallengeMethod,
    OAuth2GrantType,
    OAuth2ResponseMode,
    OAuth2ResponseType,
)
from app.models.scope import Scope

router = APIRouter()

_scopes_supported: tuple[Scope, ...] = Scope.get_basic()


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
        'scopes_supported': _scopes_supported,
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
