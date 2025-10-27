from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Literal, overload
from urllib.parse import parse_qs, urlencode

import cython
from fastapi import HTTPException, Security
from fastapi.security import SecurityScopes
from sentry_sdk import set_user
from starlette import status

from app.config import ENV
from app.lib.exceptions_context import raise_for
from app.middlewares.request_context_middleware import get_request
from app.models.db.user import User, user_is_test
from app.models.scope import Scope
from app.models.types import ApplicationId

# TODO: ACL
# TODO: more 0.7 scopes


_USER_CTX = ContextVar[User | None]('AuthUser')
_SCOPES_CTX = ContextVar[frozenset[Scope]]('AuthScopes')
_APP_CTX = ContextVar[ApplicationId | None]('AuthApp')


@contextmanager
def auth_context(
    user: User | None,
    scopes=frozenset[Scope](),
    app_id: ApplicationId | None = None,
    /,
):
    """Context manager for authenticating the user."""
    # safety check, prevent test user auth in non-test env
    if user is not None and user_is_test(user) and ENV == 'prod':
        raise RuntimeError(f'Test user authentication is disabled in {ENV} environment')

    sentry_user: dict[str, Any] = {'ip_address': '{{auto}}'}
    if user is not None:
        sentry_user['id'] = str(user['id'])  # as string, matching frontend behavior
        sentry_user['username'] = user['display_name']
        if timezone := user['timezone']:
            sentry_user['geo.region'] = timezone
    set_user(sentry_user)

    user_token = _USER_CTX.set(user)
    scopes_token = _SCOPES_CTX.set(scopes)
    app_token = _APP_CTX.set(app_id)
    try:
        yield
    finally:
        _USER_CTX.reset(user_token)
        _SCOPES_CTX.reset(scopes_token)
        _APP_CTX.reset(app_token)


@overload
def auth_user() -> User | None: ...
@overload
def auth_user(*, required: Literal[True]) -> User: ...
@overload
def auth_user(*, required: Literal[False]) -> User | None: ...
def auth_user(*, required: bool = False) -> User | None:
    """Get the authenticated user."""
    user = _USER_CTX.get()
    if user is None and required:
        raise ValueError('User must be authenticated')
    return user


def auth_scopes() -> frozenset[Scope]:
    """Get the authenticated user's scopes."""
    return _SCOPES_CTX.get()


def auth_app() -> ApplicationId | None:
    """Get the authenticated app id."""
    return _APP_CTX.get()


def api_user(*require_scopes: Scope) -> User:
    """Dependency for authenticating the api user."""
    return Security(_get_user, scopes=require_scopes)


def web_user(*require_scopes: Scope) -> User:
    """Dependency for authenticating the web user."""
    return Security(_get_user, scopes=('web_user', *require_scopes))


def _get_user(require_security_scopes: SecurityScopes) -> User:
    """
    Get the authenticated user.
    Raises an exception if the user is not authenticated or does not have the required scopes.
    """
    require_scopes = set(require_security_scopes.scopes)

    # Must be authenticated
    user = auth_user()
    if user is None:
        if (
            'web_user' not in require_scopes  #
            or get_request().url.path.startswith((
                '/api/',
                '/static',
            ))
        ):
            raise_for.unauthorized(request_basic_auth=True)
        raise HTTPException(
            status.HTTP_303_SEE_OTHER,
            headers={'Location': f'/login?{urlencode({"referer": _get_referer()})}'},
        )

    # Must have the required scopes
    require_scopes -= auth_scopes()
    if require_scopes:
        raise_for.insufficient_scopes(require_scopes)

    return user


@cython.cfunc
def _get_referer() -> str:
    """
    Get referer for the current request.
    If not explicit referer is provided, return current destination instead.
    """
    url = get_request().url
    referrers = parse_qs(url.query).get('referer')

    return (
        referrer
        # Referrer must start with '/' to avoid open redirect
        if referrers and (referrer := referrers[0])[:1] == '/'
        else f'{url.path}?{url.query}'
    )
