import logging
from base64 import b64decode
from collections.abc import Sequence

from authlib.oauth1.errors import OAuth1Error
from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy import update

from app.config import SECRET
from app.db import db_autocommit
from app.lib.buffered_random import buffered_randbytes
from app.lib.crypto import hash_bytes
from app.lib.date_utils import format_iso_date, utcnow
from app.lib.exceptions_context import raise_for
from app.lib.oauth1 import OAuth1
from app.lib.oauth2 import OAuth2
from app.limits import FAST_PASSWORD_CACHE_EXPIRE, USER_TOKEN_SESSION_EXPIRE
from app.models.db.user import User
from app.models.db.user_token_session import UserTokenSession
from app.models.msgspec.user_token_struct import UserTokenStruct
from app.models.scope import ExtendedScope, Scope
from app.repositories.user_repository import UserRepository
from app.repositories.user_token_session_repository import UserTokenSessionRepository
from app.services.cache_service import CacheService
from app.services.oauth1_nonce_service import OAuth1NonceService
from app.validators.email import validate_email

_cache_context = 'FastPassword'

# all scopes when using basic auth
_basic_auth_scopes = tuple(Scope.__members__.values())

# all scopes when using session auth
_session_auth_scopes = (*_basic_auth_scopes, ExtendedScope.web_user)


class AuthService:
    @staticmethod
    async def authenticate_request(request: Request) -> tuple[User | None, Sequence[ExtendedScope]]:
        """
        Authenticate with the request.

        API endpoints support basic auth and oauth.

        All endpoints support session cookies.

        Returns the authenticated user (if any) and scopes.
        """

        user, scopes = None, ()

        # api endpoints support basic auth and oauth
        if request.url.path.startswith(('/api/0.6/', '/api/0.7/')):
            authorization = request.headers.get('Authorization')
            scheme, param = get_authorization_scheme_param(authorization)

            # handle basic auth
            if scheme == 'Basic':
                logging.debug('Attempting to authenticate with Basic')
                username, _, password = b64decode(param).decode().partition(':')
                if not username or not password:
                    raise_for().bad_basic_auth_format()

                basic_user = await AuthService.authenticate_credentials(username, password, basic_request=request)
                if basic_user is not None:
                    user, scopes = basic_user, _basic_auth_scopes

            # handle oauth
            else:
                # don't rely on scheme header for oauth, 1.0 may use query params
                logging.debug('Attempting to authenticate with OAuth')
                oauth_result = await AuthService.authenticate_oauth(request)
                if oauth_result is not None:
                    user = oauth_result[0]
                    scopes = oauth_result[1]

        # all endpoints support session cookies
        if user is None and (token_str := request.session.get('session')) is not None:
            logging.debug('Attempting to authenticate with cookies')
            token_struct = UserTokenStruct.from_str(token_str)
            session_user = await AuthService.authenticate_session(token_struct)
            if session_user is not None:
                user, scopes = session_user, _session_auth_scopes

        if user is not None:
            logging.debug('Request authenticated as user %d', user.id)
            scopes = (*scopes, *user.extended_scopes)
        else:
            logging.debug('Request is not authenticated')

        return user, scopes

    @staticmethod
    async def authenticate_credentials(
        display_name_or_email: str,
        password: str,
        *,
        basic_request: Request | None,
    ) -> User | None:
        """
        Authenticate a user by (display name or email) and password.

        If `basic_request` is provided, the password will be cached for a short time.

        Returns `None` if the user is not found or the password is incorrect.
        """

        # TODO: normalize unicode & strip

        # dot in string indicates email, display name can't have a dot
        if '.' in display_name_or_email:
            try:
                email = validate_email(display_name_or_email)
                user = await UserRepository.find_one_by_email(email)
            except ValueError:
                user = None
        else:
            display_name = display_name_or_email
            user = await UserRepository.find_one_by_display_name(display_name)

        if user is None:
            logging.debug('User not found %r', display_name_or_email)
            return None

        # fast password cache with extra entropy
        # used primarily for api basic auth user:pass which is a hot spot
        if basic_request is not None:
            key = '\0'.join(
                (
                    SECRET,
                    user.password_hashed,
                    format_iso_date(user.password_changed_at),
                    basic_request.client.host,
                    basic_request.headers.get('User-Agent', ''),
                    password,
                )
            )

            async def factory() -> bytes:
                logging.debug('Fast password cache miss for user %r', user.id)
                ph = user.password_hasher
                ph_valid = ph.verify(user.password_hashed, user.password_salt, password)
                return b'\xff' if ph_valid else b'\x00'

            cache = await CacheService.get_one_by_key(key, _cache_context, factory, ttl=FAST_PASSWORD_CACHE_EXPIRE)
        else:
            cache = None

        if cache is not None:
            ph = None
            ph_valid = cache.value == b'\xff'
        else:
            ph = user.password_hasher
            ph_valid = ph.verify(user.password_hashed, user.password_salt, password)

        if not ph_valid:
            logging.debug('Password mismatch for user %r', user.id)
            return None

        if ph is not None and ph.rehash_needed:
            new_hash = ph.hash(password)

            async with db_autocommit() as session:
                stmt = (
                    update(User)
                    .where(User.id == user.id, User.password_hashed == user.password_hashed)
                    .values({User.password_hashed: new_hash, User.password_salt: None})
                )

                await session.execute(stmt)

            user.password_hashed = new_hash
            user.password_salt = None
            logging.debug('Rehashed password for user %r', user.id)

        return user

    @staticmethod
    async def create_session(user_id: int) -> UserTokenStruct:
        """
        Create a new user session token.
        """

        token_bytes = buffered_randbytes(32)
        token_hashed = hash_bytes(token_bytes, context=None)

        async with db_autocommit() as session:
            token = UserTokenSession(
                user_id=user_id,
                token_hashed=token_hashed,
                expires_at=utcnow() + USER_TOKEN_SESSION_EXPIRE,
            )

            session.add(token)

            # TODO: test token.id assigned

        return UserTokenStruct.v1(id=token.id, token=token_bytes)

    @staticmethod
    async def authenticate_session(token_struct: UserTokenStruct) -> User | None:
        """
        Authenticate a user by user session token.

        Returns `None` if the session is not found or the session key is incorrect.
        """

        token = await UserTokenSessionRepository.find_one_by_token_struct(token_struct)

        if token is None:
            logging.debug('Session not found %r', token_struct.id)
            return None

        return token.user

    @staticmethod
    async def authenticate_oauth(request: Request) -> tuple[User, Sequence[Scope]] | None:
        """
        Authenticate a user by OAuth1.0 or OAuth2.0.

        Returns `None` if the request is not an OAuth request.

        Raises `OAuthError` if the request is an invalid OAuth request.
        """

        authorization = request.headers.get('Authorization')

        if authorization is None:
            # oauth1 requests may use query params or body params
            oauth_version = 1
        else:
            scheme = get_authorization_scheme_param(authorization)[0]

            if scheme == 'OAuth':
                oauth_version = 1
            elif scheme == 'Bearer':
                oauth_version = 2
            else:
                # not an OAuth request
                return None

        if oauth_version == 1:
            try:
                request_ = await OAuth1.convert_request(request)
            except OAuth1Error:
                # not an OAuth request
                return None

            if request_.signature is None:
                # not an OAuth request
                return None

            nonce = request_.oauth_params.get('oauth_nonce')
            timestamp = request_.timestamp
            await OAuth1NonceService.spend(nonce, timestamp)

            token = await OAuth1.parse_and_validate(request_)
        elif oauth_version == 2:
            token = await OAuth2.parse_and_validate(request)
        else:
            raise NotImplementedError(f'Unsupported OAuth version {oauth_version}')

        if token.authorized_at is None:
            raise_for().oauth_bad_user_token()

        return token.user, token.scopes
