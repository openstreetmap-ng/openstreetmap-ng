import logging
from base64 import b64decode
from collections.abc import Sequence
from contextlib import asynccontextmanager
from contextvars import ContextVar
from itertools import chain

from fastapi import Request, Security
from fastapi.security import SecurityScopes
from fastapi.security.utils import get_authorization_scheme_param

from lib.exceptions import raise_for
from models.db.user import User
from models.scope import ExtendedScope, Scope

# TODO: ACL
# TODO: role scopes
# TODO: more 0.7 scopes?


_context = ContextVar('Auth_context')


@asynccontextmanager
async def auth_context(request: Request):
    """
    Context manager for authenticating the user.

    For /api/ endpoints, it authenticates the user with Basic or OAuth.

    For other endpoints, it authenticates the user with session cookies.
    """

    user, scopes = None, ()

    # for /api/, use Basic or OAuth authentication
    if request.url.path.startswith('/api/'):
        authorization = request.headers.get('authorization')
        scheme, param = get_authorization_scheme_param(authorization)
        scheme = scheme.lower()

        if scheme == 'basic':
            logging.debug('Attempting to authenticate with Basic')
            username, _, password = b64decode(param).decode().partition(':')
            if not username or not password:
                raise_for().bad_basic_auth_format()
            user = await User.authenticate(username, password, basic_request=request)
            scopes = Scope.__members__.values()  # all scopes

        else:
            # NOTE: don't rely on scheme for oauth, 1.0 may use query params
            logging.debug('Attempting to authenticate with OAuth')
            if result := await User.authenticate_oauth(request):
                user, scopes = result

    # otherwise, use session cookies
    else:
        logging.debug('Attempting to authenticate with cookies')
        if (session_id := request.session.get('session_id')) and (session_key := request.session.get('session_key')):
            user = await User.authenticate_session(session_id, session_key)
            scopes = Scope.__members__.values()  # all scopes

    if user:
        logging.debug('Request authenticated as user %d', user.id)
        role_scopes = set()

        if user.terms_accepted_at:
            role_scopes.add(ExtendedScope.terms_accepted)

        # extend scopes with role-specific scopes
        if user.is_moderator:
            role_scopes.add(ExtendedScope.role_moderator)
        if user.is_administrator:
            role_scopes.add(ExtendedScope.role_moderator)
            role_scopes.add(ExtendedScope.role_administrator)

        if role_scopes:
            scopes = tuple(chain(scopes, role_scopes))
    else:
        logging.debug('Request is not authenticated')

    token = _context.set((user, scopes))
    try:
        yield
    finally:
        _context.reset(token)


def auth_user_scopes() -> tuple[User | None, Sequence[ExtendedScope]]:
    """
    Get the authenticated user and scopes.
    """

    return _context.get()


def auth_user() -> User | None:
    """
    Get the authenticated user.
    """

    return _context.get()[0]


def auth_scopes() -> Sequence[ExtendedScope]:
    """
    Get the authenticated user's scopes.
    """

    return _context.get()[1]


def _get_api_user(require_scopes: SecurityScopes) -> User:
    user, user_scopes = auth_user_scopes()
    if not user:
        raise_for().unauthorized(request_basic_auth=True)
    if missing_scopes := set(require_scopes.scopes).difference(s.value for s in user_scopes):
        raise_for().insufficient_scopes(missing_scopes)
    return user


def api_user(*require_scopes: Scope | ExtendedScope) -> User:
    """
    Dependency for authenticating the api user.
    """

    return Security(
        _get_api_user,
        scopes=tuple(
            chain(
                (s.value for s in require_scopes),
                (ExtendedScope.terms_accepted,),  # always require terms accepted
            )
        ),
    )
