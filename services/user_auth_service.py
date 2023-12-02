import logging
from collections.abc import Sequence
from hmac import compare_digest
from uuid import UUID

from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param

from config import SECRET
from db import DB
from lib.crypto import hash_b
from lib.exceptions import raise_for
from lib.oauth1 import OAuth1
from lib.oauth2 import OAuth2
from lib.password_hash import PasswordHash
from models.db.user import User
from models.scope import Scope
from repositories.user_repository import UserRepository
from repositories.user_token_session_repository import UserTokenSessionRepository
from services.cache_service import CacheService
from services.oauth1_nonce_service import OAuth1NonceService

_CACHE_CONTEXT = 'FastPassword'


class UserAuthService:
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

        user = await UserRepository.find_one_by_display_name_or_email(display_name_or_email)

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
                ph = PasswordHash(user.password_hasher)
                ph_valid = ph.verify(user.password_hashed, user.password_salt, password)
                return 'OK' if ph_valid else ''

            # TODO: FAST_PASSWORD_CACHE_EXPIRE
            cache = await CacheService.get_one_by_key(key, _CACHE_CONTEXT, factory)
        else:
            cache = None

        if cache:
            ph = None
            ph_valid = cache.value == 'OK'
        else:
            ph = PasswordHash(user.password_hasher)
            ph_valid = ph.verify(user.password_hashed, user.password_salt, password)

        if not ph_valid:
            logging.debug('Password mismatch for user %r', user.id)
            return None

        if ph and ph.rehash_needed:
            async with DB() as session, session.begin():
                user = await session.get(User, user.id, with_for_update=True)
                user.password_hashed = ph.hash(password)
                user.password_salt = None
                logging.debug('Rehashed password for user %r', user.id)

        return user

    @staticmethod
    async def authenticate_session(session_id: UUID, token_str: str) -> User | None:
        """
        Authenticate a user by session ID and session key.

        Returns `None` if the session is not found or the session key is incorrect.
        """

        token = await UserTokenSessionRepository.find_one_by_id(session_id)

        if not token:
            logging.debug('Session (or user) not found %r', session_id)
            return None

        token_hashed = hash_b(token_str, context=None)

        if not compare_digest(token.token_hashed, token_hashed):
            logging.debug('Session key mismatch for session %r', session_id)
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
