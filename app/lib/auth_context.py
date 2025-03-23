from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal, overload
from urllib.parse import parse_qs, urlencode

import cython
from fastapi import HTTPException, Security
from fastapi.security import SecurityScopes
from starlette import status

from app.config import TEST_ENV
from app.lib.exceptions_context import raise_for
from app.middlewares.request_context_middleware import get_request
from app.models.db.user import User, user_is_test
from app.models.scope import Scope

# TODO: ACL
# TODO: more 0.7 scopes


_CTX: ContextVar[tuple[User | None, tuple[Scope, ...]]] = ContextVar('Auth')


@contextmanager
def auth_context(user: User | None, scopes: tuple[Scope, ...]):
    """Context manager for authenticating the user."""
    # safety check, prevent test user auth in non-test env
    if (user is not None) and not TEST_ENV and user_is_test(user):
        raise RuntimeError('Test user authentication is forbidden in non-test environment')

    token = _CTX.set((user, scopes))
    try:
        yield
    finally:
        _CTX.reset(token)


def auth_user_scopes() -> tuple[User | None, tuple[Scope, ...]]:
    """Get the authenticated user and scopes."""
    return _CTX.get()


@overload
def auth_user() -> User | None: ...
@overload
def auth_user(*, required: Literal[True]) -> User: ...
@overload
def auth_user(*, required: Literal[False]) -> User | None: ...
def auth_user(*, required: bool = False) -> User | None:
    """Get the authenticated user."""
    user = _CTX.get()[0]
    if user is None and required:
        raise ValueError('User must be authenticated')
    return user


def auth_scopes() -> tuple[Scope, ...]:
    """Get the authenticated user's scopes."""
    return _CTX.get()[1]


def api_user(*require_scopes: Scope) -> User:
    """Dependency for authenticating the api user."""
    return Security(_get_user, scopes=require_scopes)


def web_user() -> User:
    """Dependency for authenticating the web user."""
    return Security(_get_user, scopes=('web_user',))


def _get_user(require_security_scopes: SecurityScopes) -> User:
    """
    Get the authenticated user.
    Raises an exception if the user is not authenticated or does not have the required scopes.
    """
    require_scopes = require_security_scopes.scopes
    user, user_scopes = auth_user_scopes()

    # Must be authenticated
    if user is None:
        if 'web_user' not in require_scopes or get_request().url.path.startswith(('/api/', '/static')):
            raise_for.unauthorized(request_basic_auth=True)
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={'Location': f'/login?{urlencode({"referer": _get_referer()})}'},
        )

    # Must have the required scopes
    if missing_scopes := set(require_scopes).difference(user_scopes):
        raise_for.insufficient_scopes(missing_scopes)

    return user


@cython.cfunc
def _get_referer() -> str:
    """
    Get referer for the current request.
    If not explicit referer is provided, return current destination instead.
    """
    request_url = get_request().url
    referrers = parse_qs(request_url.query).get('referer')
    if referrers is None:
        return request_url.path

    # Referrer must start with '/' to avoid open redirect
    referrer = referrers[0]
    if referrer[0].startswith('/'):
        return referrer[0]

    return f'{request_url.path}?{request_url.query}'
