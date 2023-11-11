import logging
from abc import ABC
from base64 import b64decode
from contextlib import asynccontextmanager
from contextvars import ContextVar
from itertools import chain
from typing import Sequence

from fastapi import Request, Security
from fastapi.security import SecurityScopes
from fastapi.security.utils import get_authorization_scheme_param

from lib.exceptions import Exceptions
from models.db.user import User
from models.scope import ExtendedScope, Scope

# TODO: ACL
# TODO: role scopes
# TODO: more 0.7 scopes?


class Auth(ABC):
    _context = ContextVar('Auth_context')

    @classmethod
    @asynccontextmanager
    async def auth_context(cls, request: Request):
        '''
        Context manager for authenticating the user.

        For /api/ endpoints, it authenticates the user with Basic or OAuth.

        For other endpoints, it authenticates the user with session cookies.
        '''

        user, scopes = None, ()

        if request.url.path.startswith('/api/'):
            authorization = request.headers.get('authorization')
            scheme, param = get_authorization_scheme_param(authorization)
            scheme = scheme.lower()

            if scheme == 'basic':
                logging.debug('Attempting to authenticate with Basic')
                username, _, password = b64decode(param).decode().partition(':')
                if not username or not password:
                    Exceptions.get().raise_for_bad_basic_auth_format()
                user = await User.authenticate(username, password, basic_request=request)
                scopes = Scope.__members__.values()  # all scopes

            else:  # don't rely on scheme, oauth 1.0 may use query params
                logging.debug('Attempting to authenticate with OAuth')
                if result := await User.authenticate_oauth(request):
                    user, scopes = result

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

        token = cls._context.set((user, scopes))
        try:
            yield
        finally:
            cls._context.reset(token)

    @classmethod
    def user_scopes(cls) -> tuple[User | None, Sequence[ExtendedScope]]:
        '''
        Get the authenticated user and scopes from ContextVar.
        '''

        return cls._context.get()

    @classmethod
    def user(cls) -> User | None:
        '''
        Get the authenticated user from ContextVar.
        '''

        return cls._context.get()[0]

    @classmethod
    def scopes(cls) -> Sequence[ExtendedScope]:
        '''
        Get the authenticated user's scopes from ContextVar.
        '''

        return cls._context.get()[1]


def _get_api_user(scopes: SecurityScopes) -> User:
    user, user_scopes = Auth.user_scopes()
    if not user:
        Exceptions.get().raise_for_unauthorized(request_basic_auth=True)
    if missing_scopes := set(scopes.scopes).difference(s.value for s in user_scopes):
        Exceptions.get().raise_for_insufficient_scopes(missing_scopes)
    return user


def api_user(*scopes: Scope | ExtendedScope) -> User:
    '''
    Dependency for authenticating the api user.
    '''

    return Security(_get_api_user, scopes=tuple(chain((s.value for s in scopes), (ExtendedScope.terms_accepted,))))
