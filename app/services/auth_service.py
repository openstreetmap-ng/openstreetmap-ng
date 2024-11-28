import logging

from sqlalchemy.orm import joinedload

from app.config import TEST_ENV
from app.lib.exceptions_context import raise_for
from app.lib.options_context import options_context
from app.middlewares.request_context_middleware import get_request
from app.models.db.oauth2_token import OAuth2Token
from app.models.db.user import User
from app.models.scope import PUBLIC_SCOPES, Scope
from app.models.types import DisplayNameType
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery

# default scopes when using session auth
_session_auth_scopes: tuple[Scope, ...] = (*PUBLIC_SCOPES, Scope.web_user)


class AuthService:
    @staticmethod
    async def authenticate_request() -> tuple[User | None, tuple[Scope, ...]]:
        """
        Authenticate with the request.

        API endpoints support basic auth and oauth.

        All endpoints support session cookies.

        Returns the authenticated user (if any) and scopes.
        """
        user: User | None = None
        scopes: tuple[Scope, ...] = ()
        request = get_request()
        request_path: str = request.url.path

        # skip authorization for static requests
        if request_path.startswith('/static'):
            return user, scopes

        scheme: str
        param: str

        # application endpoints support basic auth and oauth
        if request_path.startswith(('/api/0.6/', '/api/0.7/', '/oauth2/')):
            authorization = request.headers.get('Authorization')
            if authorization is not None:
                scheme, _, param = authorization.partition(' ')
            else:
                scheme = param = ''

            # support access_token in form (https://datatracker.ietf.org/doc/html/rfc6750#section-2.2)
            if (
                not scheme
                and request.method == 'POST'
                and request.headers.get('Content-Type') == 'application/x-www-form-urlencoded'
            ):
                access_token = (await request.form()).get('access_token')
                if access_token is not None and isinstance(access_token, str):
                    scheme = 'bearer'
                    param = access_token

            # handle oauth2
            if scheme.casefold() == 'bearer':
                logging.debug('Attempting to authenticate with OAuth2')
                oauth_result = await AuthService.authenticate_oauth2(param)
                if oauth_result is not None:
                    user = oauth_result.user
                    scopes = oauth_result.scopes

        # all endpoints support session cookies
        if user is None and (token_str := request.cookies.get('auth')) is not None:
            logging.debug('Attempting to authenticate with cookies')
            oauth_result = await AuthService.authenticate_oauth2(token_str)
            if (oauth_result is not None) and oauth_result.scopes == (Scope.web_user,):
                user = oauth_result.user
                scopes = _session_auth_scopes

        # all endpoints on test env support any user auth
        if user is None and TEST_ENV:
            authorization = request.headers.get('Authorization')
            if authorization is not None:
                scheme, _, param = authorization.partition(' ')
                if scheme.casefold() == 'user':
                    logging.debug('Attempting to authenticate with User')
                    user = await UserQuery.find_one_by_display_name(DisplayNameType(param))
                    scopes = _session_auth_scopes
                    if user is None:
                        raise_for.user_not_found(param)

        if user is not None:
            logging.debug('Request authenticated as user %d', user.id)
            scopes = user.extend_scopes(scopes)

        return user, scopes

    @staticmethod
    async def authenticate_oauth2(param: str | None) -> OAuth2Token | None:
        """
        Authenticate a user with OAuth2.

        If param is None, it will be read from the request cookies.

        Returns None if the token is not found.

        Raises an exception if the token is not authorized.
        """
        if param is None:
            param = get_request().cookies.get('auth')
            if param is None:
                return None
        with options_context(joinedload(OAuth2Token.user)):
            token = await OAuth2TokenQuery.find_one_authorized_by_token(param)
        if token is None:
            return None
        if token.authorized_at is None:
            raise_for.oauth_bad_user_token()
        return token
