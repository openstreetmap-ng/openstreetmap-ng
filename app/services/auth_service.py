import logging

from fastapi import Request
from pydantic import SecretStr

from app.config import ENV
from app.lib.testmethod import testmethod
from app.middlewares.request_context_middleware import get_request
from app.models.db.oauth2_token import OAuth2Token
from app.models.db.user import User, user_extend_scopes
from app.models.scope import PUBLIC_SCOPES, Scope
from app.models.types import ApplicationId, DisplayName
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery
from app.services.audit_service import audit

# default scopes when using session auth
_SESSION_AUTH_SCOPES: frozenset[Scope] = PUBLIC_SCOPES | {'web_user'}  # type: ignore
_EMPTY_SCOPES = frozenset[Scope]()


class AuthService:
    @staticmethod
    async def authenticate_request() -> tuple[
        User | None, frozenset[Scope], ApplicationId | None
    ]:
        """Authenticate the request. Returns the authenticated user (if any) and scopes."""
        req = get_request()
        path: str = req.url.path

        # Skip authentication for static requests
        if path.startswith('/static'):
            return None, _EMPTY_SCOPES, None

        # Try OAuth2 authentication for API endpoints
        if path.startswith(('/api/0.6/', '/api/0.7/', '/oauth2/')):
            r = await _authenticate_with_oauth2(req)
            if r is not None:
                return r

        # Try session cookie authentication
        r = await _authenticate_with_cookie(req)
        if r is not None:
            return r

        # Try test user authentication if in test environment
        if ENV != 'prod':
            r = await _authenticate_with_test_user(req)
            if r is not None:
                return r

        return None, _EMPTY_SCOPES, None

    @staticmethod
    async def authenticate_oauth2(access_token: SecretStr | None) -> OAuth2Token | None:
        """
        Authenticate a user with OAuth2.
        If param is None, it will be read from the request cookies.
        Returns None if the token is not found, or if it is not authorized.
        """
        if access_token is None:
            auth = get_request().cookies.get('auth')
            if auth is None:
                return None
            access_token = SecretStr(auth)
            del auth

        token = await OAuth2TokenQuery.find_authorized_by_token(access_token)
        if token is None or token['authorized_at'] is None:
            return None

        return token


async def _extract_oauth2_token(request: Request) -> SecretStr | None:
    # Check in Authorization header
    authorization = request.headers.get('Authorization')
    if authorization:
        scheme, _, param = authorization.partition(' ')
        return SecretStr(param) if scheme.casefold() == 'bearer' and param else None

    # Check in form data
    if (
        request.method == 'POST'
        and request.headers.get('Content-Type') == 'application/x-www-form-urlencoded'
    ):
        value = (await request.form()).get('access_token')
        return SecretStr(value) if value and isinstance(value, str) else None

    return None


async def _authenticate_with_oauth2(
    request: Request,
) -> tuple[User, frozenset[Scope], ApplicationId] | None:
    access_token = await _extract_oauth2_token(request)
    if access_token is None:
        return None

    logging.debug('Attempting to authenticate with OAuth2')
    token = await AuthService.authenticate_oauth2(access_token)
    if token is None:
        return None

    user_id = token['user_id']
    user = await UserQuery.find_by_id(user_id)
    if user is None:
        return None

    application_id = token['application_id']
    audit('auth_api', user_id=user_id, application_id=application_id)  # pyright: ignore[reportUnusedCoroutine]
    scopes = user_extend_scopes(user, frozenset(token['scopes']))
    return user, scopes, application_id


async def _authenticate_with_cookie(
    request: Request,
) -> tuple[User, frozenset[Scope], None] | None:
    auth = request.cookies.get('auth')
    if auth is None:
        return None
    access_token = SecretStr(auth)
    del auth

    logging.debug('Attempting to authenticate with cookies')
    token = await AuthService.authenticate_oauth2(access_token)
    if token is None or token['scopes'] != ['web_user']:
        return None

    user_id = token['user_id']
    user = await UserQuery.find_by_id(user_id)
    if user is None:
        return None

    audit('auth_web', user_id=user_id, application_id=None)  # pyright: ignore[reportUnusedCoroutine]
    scopes = user_extend_scopes(user, _SESSION_AUTH_SCOPES)
    return user, scopes, None


@testmethod
async def _authenticate_with_test_user(
    request: Request,
) -> tuple[User, frozenset[Scope]] | None:
    authorization = request.headers.get('Authorization')
    if authorization is None:
        return None

    scheme, _, param = authorization.partition(' ')
    if scheme.casefold() != 'user':
        return None

    logging.debug('Attempting to authenticate with test user %r', param)
    user_display_name = DisplayName(param)
    user = await UserQuery.find_by_display_name(user_display_name)
    assert user is not None

    scopes = user_extend_scopes(user, _SESSION_AUTH_SCOPES)
    return user, scopes
