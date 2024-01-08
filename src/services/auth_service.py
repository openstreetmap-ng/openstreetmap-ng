import logging
import secrets
from collections.abc import Sequence

from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy import update

from src.config import SECRET
from src.db import DB
from src.lib.crypto import hash_b
from src.lib.email import Email
from src.lib.exceptions import raise_for
from src.lib.oauth1 import OAuth1
from src.lib.oauth2 import OAuth2
from src.limits import USER_TOKEN_SESSION_EXPIRE
from src.models.db.user import User
from src.models.db.user_token_session import UserTokenSession
from src.models.msgspec.user_token_struct import UserTokenStruct
from src.models.scope import Scope
from src.repositories.user_repository import UserRepository
from src.repositories.user_token_session_repository import UserTokenSessionRepository
from src.services.cache_service import CacheService
from src.services.oauth1_nonce_service import OAuth1NonceService
from src.utils import utcnow

_CACHE_CONTEXT = 'FastPassword'


class AuthService:
    @staticmethod
    async def authenticate(
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
                email = display_name_or_email
                email = Email.validate(email)
                user = await UserRepository.find_one_by_email(email)
            except ValueError:
                user = None
        else:
            display_name = display_name_or_email
            user = await UserRepository.find_one_by_display_name(display_name)

        if not user:
            logging.debug('User not found %r', display_name_or_email)
            return None

        # fast password cache with extra entropy
        # used primarily for api basic auth user:pass which is a hot spot
        if basic_request:
            key = '\0'.join(
                (
                    SECRET,
                    user.password_hashed,
                    basic_request.client.host,
                    basic_request.headers.get('user-agent', ''),
                    password,
                )
            )

            async def factory() -> str:
                logging.debug('Fast password cache miss for user %r', user.id)
                ph = user.password_hasher
                ph_valid = ph.verify(user.password_hashed, user.password_salt, password)
                return 'OK' if ph_valid else ''

            # TODO: FAST_PASSWORD_CACHE_EXPIRE
            # TODO: expire on pass change
            cache = await CacheService.get_one_by_key(key, _CACHE_CONTEXT, factory)
        else:
            cache = None

        if cache:
            ph = None
            ph_valid = cache.value == 'OK'
        else:
            ph = user.password_hasher
            ph_valid = ph.verify(user.password_hashed, user.password_salt, password)

        if not ph_valid:
            logging.debug('Password mismatch for user %r', user.id)
            return None

        if ph and ph.rehash_needed:
            new_hash = ph.hash(password)

            async with DB() as session:
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

        token_b = secrets.token_bytes(32)
        token_hashed = hash_b(token_b, context=None)

        async with DB() as session:
            token = UserTokenSession(
                user_id=user_id,
                token_hashed=token_hashed,
                expires_at=utcnow() + USER_TOKEN_SESSION_EXPIRE,
            )

            session.add(token)

        return UserTokenStruct(token.id, token_b)

    @staticmethod
    async def authenticate_session(token_struct: UserTokenStruct) -> User | None:
        """
        Authenticate a user by user session token.

        Returns `None` if the session is not found or the session key is incorrect.
        """

        token = await UserTokenSessionRepository.find_one_by_token_struct(token_struct)

        if not token:
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

        authorization = request.headers.get('authorization')

        if not authorization:
            # oauth1 requests may use query params or body params
            oauth_version = 1
        else:
            scheme, _ = get_authorization_scheme_param(authorization)
            scheme = scheme.lower()

            if scheme == 'oauth':
                oauth_version = 1
            elif scheme == 'bearer':
                oauth_version = 2
            else:
                # not an OAuth request
                return None

        if oauth_version == 1:
            request_ = await OAuth1.convert_request(request)

            if not request_.signature:
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

        if not token.authorized_at:
            raise_for().oauth_bad_user_token()

        return token.user, token.scopes
