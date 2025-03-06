import logging

from fastapi import Request
from pydantic import SecretStr

from app.config import TEST_ENV
from app.lib.exceptions_context import raise_for
from app.lib.testmethod import testmethod
from app.middlewares.request_context_middleware import get_request
from app.models.db.oauth2_token import OAuth2Token
from app.models.db.user import User, user_extend_scopes
from app.models.scope import PUBLIC_SCOPES, Scope
from app.models.types import DisplayName
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery

# default scopes when using session auth
_SESSION_AUTH_SCOPES: tuple[Scope, ...] = (*PUBLIC_SCOPES, 'web_user')


class AuthService:
    @staticmethod
    async def authenticate_request() -> tuple[User | None, tuple[Scope, ...]]:
        """Authenticate the request. Returns the authenticated user (if any) and scopes."""
        request = get_request()
        request_path: str = request.url.path

        # Skip authentication for static requests
        if request_path.startswith('/static'):
            return None, ()

        # Try OAuth2 authentication for API endpoints
        if request_path.startswith(('/api/0.6/', '/api/0.7/', '/oauth2/')):
            r = await _authenticate_with_oauth2(request)
            if r is not None:
                return r[0], r[1]

        # Try session cookie authentication
        r = await _authenticate_with_cookie(request)
        if r is not None:
            return r[0], r[1]

        # Try test user authentication if in test environment
        if TEST_ENV:
            r = await _authenticate_with_test_user(request)
            if r is not None:
                return r[0], r[1]

        return None, ()

    @staticmethod
    async def authenticate_oauth2(access_token: SecretStr | None) -> OAuth2Token | None:
        """
        Authenticate a user with OAuth2.

        If param is None, it will be read from the request cookies.

        Returns None if the token is not found.

        Raises an exception if the token is not authorized.
        """
        if access_token is None:
            auth = get_request().cookies.get('auth')
            if auth is None:
                return None
            access_token = SecretStr(auth)
            del auth

        token = await OAuth2TokenQuery.find_one_authorized_by_token(access_token)
        if token is None:
            return None

        if token['authorized_at'] is None:
            raise_for.oauth_bad_user_token()

        return token


async def _extract_oauth2_token(request: Request) -> SecretStr | None:
    # Check in Authorization header
    authorization = request.headers.get('Authorization')
    if authorization:
        scheme, _, param = authorization.partition(' ')
        return SecretStr(param) if scheme.casefold() == 'bearer' and param else None

    # Check in form data
    if request.method == 'POST' and request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
        value = (await request.form()).get('access_token')
        return SecretStr(value) if value and isinstance(value, str) else None

    return None


async def _authenticate_with_oauth2(request: Request) -> tuple[User, tuple[Scope, ...]] | None:
    access_token = await _extract_oauth2_token(request)
    if access_token is None:
        return None

    logging.debug('Attempting to authenticate with OAuth2')
    token = await AuthService.authenticate_oauth2(access_token)
    if token is None:
        return None

    user = await UserQuery.find_one_by_id(token['user_id'])
    if user is None:
        return None

    scopes = user_extend_scopes(user, tuple(token['scopes']))
    return user, scopes


async def _authenticate_with_cookie(request: Request) -> tuple[User, tuple[Scope, ...]] | None:
    auth = request.cookies.get('auth')
    if auth is None:
        return None
    access_token = SecretStr(auth)
    del auth

    logging.debug('Attempting to authenticate with cookies')
    token = await AuthService.authenticate_oauth2(access_token)
    if token is None or token['scopes'] != ['web_user']:
        return None

    user = await UserQuery.find_one_by_id(token['user_id'])
    if user is None:
        return None

    scopes = user_extend_scopes(user, _SESSION_AUTH_SCOPES)
    return user, scopes


@testmethod
async def _authenticate_with_test_user(request: Request) -> tuple[User, tuple[Scope, ...]] | None:
    authorization = request.headers.get('Authorization')
    if authorization is None:
        return None

    scheme, _, param = authorization.partition(' ')
    if scheme.casefold() != 'user':
        return None

    logging.debug('Attempting to authenticate with test user %r', param)
    user = await UserQuery.find_one_by_display_name(DisplayName(param))
    if user is None:
        raise_for.user_not_found(param)

    scopes = user_extend_scopes(user, _SESSION_AUTH_SCOPES)
    return user, scopes
