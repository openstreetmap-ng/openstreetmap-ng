from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal, overload

import cython
from fastapi import Security
from fastapi.security import SecurityScopes

from app.config import TEST_ENV, TEST_USER_DOMAIN
from app.lib.exceptions_context import raise_for
from app.models.db.user import User
from app.models.scope import Scope

# TODO: ACL
# TODO: more 0.7 scopes


_context: ContextVar[tuple[User | None, tuple[Scope, ...]]] = ContextVar('AuthContext')


@contextmanager
def auth_context(user: User | None, scopes: tuple[Scope, ...]):
    """
    Context manager for authenticating the user.
    """
    # safety check, prevent test user auth in non-test env
    if (user is not None) and not TEST_ENV and user.email.endswith('@' + TEST_USER_DOMAIN):
        raise RuntimeError('Test user authentication is forbidden in non-test environment')

    token = _context.set((user, scopes))
    try:
        yield
    finally:
        _context.reset(token)


def auth_user_scopes() -> tuple[User | None, tuple[Scope, ...]]:
    """
    Get the authenticated user and scopes.
    """
    return _context.get()


@overload
def auth_user() -> User | None: ...


@overload
def auth_user(*, required: Literal[True]) -> User: ...


@overload
def auth_user(*, required: Literal[False]) -> User | None: ...


def auth_user(*, required: bool = False) -> User | None:
    """
    Get the authenticated user.
    """
    user = _context.get()[0]
    if user is None and required is True:
        raise ValueError('User must be authenticated')
    return user


def auth_scopes() -> tuple[Scope, ...]:
    """
    Get the authenticated user's scopes.
    """
    return _context.get()[1]


def api_user(*require_scopes: Scope) -> User:
    """
    Dependency for authenticating the api user.
    """
    return Security(_get_user, scopes=require_scopes)


def web_user() -> User:
    """
    Dependency for authenticating the web user.
    """
    return Security(_get_user, scopes=(Scope.web_user,))


@cython.cfunc
def _get_user(require_scopes: SecurityScopes):
    """
    Get the authenticated user.

    Raises an exception if the user is not authenticated or does not have the required scopes.
    """
    user, user_scopes = auth_user_scopes()
    # user must be authenticated
    if user is None:
        request_basic_auth = Scope.web_user not in require_scopes.scopes
        raise_for().unauthorized(request_basic_auth=request_basic_auth)
    # and have the required scopes
    if missing_scopes := set(require_scopes.scopes).difference(user_scopes):
        raise_for().insufficient_scopes(missing_scopes)
    return user
