import logging
from base64 import b64decode

from pydantic import SecretStr
from sqlalchemy import update
from sqlalchemy.orm import joinedload

from app.config import SECRET, TEST_ENV
from app.db import db_commit
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.lib.options_context import options_context
from app.lib.password_hash import PasswordHash
from app.limits import AUTH_CREDENTIALS_CACHE_EXPIRE
from app.middlewares.request_context_middleware import get_request
from app.models.db.oauth2_token import OAuth2Token
from app.models.db.user import User
from app.models.scope import PUBLIC_SCOPES, Scope
from app.models.types import PasswordType
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery
from app.services.cache_service import CacheContext, CacheService
from app.validators.email import validate_email

_credentials_context = CacheContext('AuthCredentials')

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

        # api endpoints support basic auth and oauth
        if request_path.startswith(('/api/0.6/', '/api/0.7/')):
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

            scheme = scheme.casefold()

            # handle basic auth
            if scheme == 'basic':
                logging.debug('Attempting to authenticate with Basic')
                username, _, password = b64decode(param).decode().partition(':')
                if not username or not password:
                    raise_for().bad_basic_auth_format()

                basic_user = await AuthService.authenticate_credentials(
                    display_name_or_email=username,
                    password=PasswordType(SecretStr(password)),
                )
                if basic_user is not None:
                    user, scopes = basic_user, PUBLIC_SCOPES

            # handle oauth2
            elif scheme == 'bearer':
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
                scheme = scheme.casefold()
                if scheme == 'user':
                    logging.debug('Attempting to authenticate with User')
                    user = await UserQuery.find_one_by_display_name(param)
                    scopes = _session_auth_scopes
                    if user is None:
                        raise_for().user_not_found(param)

        if user is not None:
            logging.debug('Request authenticated as user %d', user.id)
            scopes = user.extend_scopes(scopes)

        return user, scopes

    @staticmethod
    async def authenticate_credentials(display_name_or_email: str, password: PasswordType) -> User | None:
        """
        Authenticate a user with (display name or email) and password.

        Returns None if the user is not found or the password is incorrect.
        """
        # TODO: normalize unicode & strip
        # dot in string indicates email, display name can't have a dot
        if '.' in display_name_or_email:
            try:
                email = validate_email(display_name_or_email)
                user = await UserQuery.find_one_by_email(email)
            except ValueError:
                user = None
        else:
            display_name = display_name_or_email
            user = await UserQuery.find_one_by_display_name(display_name)

        if user is None:
            logging.debug('User not found %r', display_name_or_email)
            return None

        async def factory() -> bytes:
            logging.debug('Credentials auth cache miss for user %d', user.id)
            verified = PasswordHash.verify(user.password_hashed, password, is_test_user=user.is_test_user)

            if not verified.success:
                return b'\x00'

            if verified.rehash_needed:
                new_hash = PasswordHash.hash(password)

                async with db_commit() as session:
                    stmt = (
                        update(User)
                        .where(User.id == user.id, User.password_hashed == user.password_hashed)
                        .values({User.password_hashed: new_hash})
                        .inline()
                    )
                    await session.execute(stmt)

                user.password_hashed = new_hash
                logging.debug('Rehashed password for user %d', user.id)

            return b'\xff'

        password_hashed = user.password_hashed
        password_changed_at = user.password_changed_at
        password_changed_at_str = password_changed_at.isoformat() if (password_changed_at is not None) else 'None'

        cache_id = hash_bytes(
            f'{SECRET}\x00{password_hashed}\x00{password_changed_at_str}\x00{password.get_secret_value()}'
        )
        cache = await CacheService.get(
            cache_id,
            context=_credentials_context,
            factory=factory,
            ttl=AUTH_CREDENTIALS_CACHE_EXPIRE,
        )

        if cache.value != b'\xff':
            logging.debug('Password mismatch for user %d', user.id)
            return None

        return user

    @staticmethod
    async def authenticate_oauth2(param: str | None) -> OAuth2Token | None:
        """
        Authenticate a user with OAuth2.

        If param is None, it will be read from the request cookies.

        Returns None if the token is not found.

        Raises an exception if the token is not authorized.
        """
        # TODO: PATs
        if param is None:
            param = get_request().cookies.get('auth')
            if param is None:
                return None
        with options_context(joinedload(OAuth2Token.user)):
            token = await OAuth2TokenQuery.find_one_authorized_by_token(param)
        if token is None:
            return None
        if token.authorized_at is None:
            raise_for().oauth_bad_user_token()
        return token
