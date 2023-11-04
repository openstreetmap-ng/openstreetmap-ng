import logging
from datetime import datetime
from hmac import compare_digest
from typing import Annotated, Self, Sequence

from annotated_types import MaxLen
from argon2 import PasswordHasher
from asyncache import cached
from bson import ObjectId
from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param
from pydantic import Field
from shapely.geometry import Point

from config import DEFAULT_LANGUAGE, SECRET
from lib.avatar import Avatar
from lib.crypto import hash_hex
from lib.exceptions import Exceptions
from lib.languages import Language, fix_language_case, get_language
from lib.oauth1 import OAuth1
from lib.oauth2 import OAuth2
from lib.password_hash import PasswordHash
from lib.rich_text import RichText
from limits import (FAST_PASSWORD_CACHE_EXPIRE, NEARBY_USERS_LIMIT,
                    NEARBY_USERS_RADIUS_METERS, USER_DESCRIPTION_MAX_LENGTH)
from models.collections.base_sequential import BaseSequential
from models.collections.cache import Cache
from models.collections.oauth_nonce import OAuthNonce
from models.collections.user_token_session import UserTokenSession
from models.geometry import PointGeometry
from models.scope import Scope
from models.str import EmailStr, HexStr, NonEmptyStr, Str255, UserNameStr
from models.text_format import TextFormat
from models.user_avatar_type import UserAvatarType
from models.user_role import UserRole
from models.user_status import UserStatus
from utils import haversine_distance, utcnow


class User(BaseSequential):
    email: EmailStr
    display_name: UserNameStr
    password_hashed: NonEmptyStr
    created_ip: NonEmptyStr
    consider_public_domain: bool
    languages: tuple[Str255, ...]  # TODO: list limit
    auth_provider: NonEmptyStr | None
    auth_uid: NonEmptyStr | None

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]
    status: UserStatus = UserStatus.pending
    email_confirmed: bool = False
    password_salt: NonEmptyStr | None = None
    terms_seen: bool = False
    terms_accepted_at: datetime | None = None
    roles: Annotated[tuple[UserRole, ...], Field()] = ()
    description: Annotated[str, MaxLen(USER_DESCRIPTION_MAX_LENGTH)] = ''
    description_rich_hash: HexStr | None = None
    home_point: PointGeometry | None = None
    home_zoom: int | None = None
    avatar_type: UserAvatarType = UserAvatarType.default
    avatar_id: NonEmptyStr | None = None
    preferences: Annotated[dict[Str255, Str255], Field(default_factory=dict)]

    # TODO: tuples
    @property
    def is_administrator(self) -> bool:
        return UserRole.administrator in self.roles

    @property
    def is_moderator(self) -> bool:
        return UserRole.moderator in self.roles or self.is_administrator

    @property
    def language_str(self) -> str:
        return ' '.join(self.languages)

    @language_str.setter
    def language_str(self, s: str) -> None:
        languages = s.split()
        languages = (t.strip() for t in languages)
        languages = (fix_language_case(t) for t in languages)
        languages = (t for t in languages if t)
        self.languages = tuple(languages)

    @property
    def preferred_diary_language(self) -> Language:
        for code in self.languages:
            if lang := get_language(code):
                return lang

        return get_language(DEFAULT_LANGUAGE)

    @property
    def changeset_max_size(self) -> int:
        return UserRole.get_changeset_max_size(self.roles)

    @property
    def password_hasher(self) -> PasswordHasher:
        return UserRole.get_password_hasher(self.roles)

    @property
    def avatar_url(self) -> str:
        return Avatar.get_url(self.avatar_type, self.avatar_id)

    @cached({})
    async def description_rich(self) -> str:
        cache = await RichText.get_cache(self.description, self.description_rich_hash, TextFormat.markdown)
        if self.description_rich_hash != cache.id:
            self.description_rich_hash = cache.id
            await self.update()
        return cache.value

    @classmethod
    async def authenticate(cls, email_or_username: str, password: str, *, basic_request: Request | None) -> Self | None:
        '''
        Authenticate a user by email or username and password.

        If `basic_request` is provided, the password will be cached for a short time.

        Returns `None` if the user is not found or the password is incorrect.
        '''

        # TODO: normalize unicode & strip

        if '.' in email_or_username:
            field = 'email'
        else:
            field = 'display_name'

        user = await cls.find_one({
            '$or': [
                {field: email_or_username},
                {field: email_or_username.lower()},  # TODO: collation?
            ],
        })

        if user is None:
            logging.debug('User not found %r', email_or_username)
            return None

        # fast password cache with extra entropy
        # used primarily for api basic auth user:pass which is a hot spot
        if basic_request:
            key = '\0'.join((
                SECRET,
                user.password_hashed,
                basic_request.client.host,
                basic_request.headers.get('User-Agent', ''),
                password))

            cache_id = Cache.hash_key(key)
            cache = await Cache.find_one_by_id(cache_id)
        else:
            cache = None

        if cache:
            ph = None
            ph_valid = cache.value == 'OK'
        else:
            ph = PasswordHash(user.password_hasher)
            ph_valid = ph.verify(user.password_hashed, user.password_salt, password)
            if basic_request:
                logging.debug('Fast password cache miss for user %r', user.id)
                await Cache.create_from_key_id(cache_id, 'OK' if ph_valid else '', ttl=FAST_PASSWORD_CACHE_EXPIRE)

        if not ph_valid:
            logging.debug('Password mismatch for user %r', user.id)
            return None

        if ph and ph.rehash_needed:
            user.password_hashed = ph.hash(password)
            user.password_salt = None
            await user.update()
            logging.debug('Rehashed password for user %r', user.id)

        return user

    @classmethod
    async def authenticate_session(cls, session_id: ObjectId, session_key: str) -> Self | None:
        '''
        Authenticate a user by session ID and session key.

        Returns `None` if the session is not found or the session key is incorrect.
        '''

        pipeline = [
            {'$match': {'_id': session_id}},
            {'$lookup': {
                'from': cls._collection_name(),
                'localField': 'user_id',
                'foreignField': '_id',
                'as': 'user'
            }},
            {'$unwind': '$user'}
        ]

        cursor = UserTokenSession._collection().aggregate(pipeline)
        result = await cursor.to_list(1)

        if not result:
            logging.debug('Session (or user) not found %r', session_id)
            return None

        data: dict = result[0]
        user_d: dict = data.pop('user')
        token = UserTokenSession.model_validate(data)

        if not compare_digest(token.key_hashed, hash_hex(session_key)):
            logging.debug('Session key mismatch for session %r', session_id)
            return None

        return cls.model_validate(user_d)

    @classmethod
    async def authenticate_oauth(cls, request: Request) -> tuple[Self, Sequence[Scope]] | None:
        '''
        Authenticate a user by OAuth1.0 or OAuth2.0.

        Returns `None` if the request is not an OAuth request.

        Raises `OAuthError` if the request is an invalid OAuth request.
        '''

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

            OAuthNonce.spend(request_.oauth_params.get('oauth_nonce'), request_.timestamp)

            token = await OAuth1.parse_and_validate(request_)
        elif oauth_version == 2:
            token = await OAuth2.parse_and_validate(request)
        else:
            raise NotImplementedError(f'Unsupported OAuth version {oauth_version}')

        if not token.authorized_at or token.revoked_at:
            Exceptions.get().raise_for_oauth_bad_user_token()

        user = await cls.find_one_by_id(token.user_id)

        if not user:
            Exceptions.get().raise_for_oauth_bad_user_token()

        return user, token.scopes

    @classmethod
    async def find_one_by_display_name(cls, display_name: str) -> Self | None:
        return await cls.find_one({'display_name': display_name})  # TODO: collation

    @classmethod
    async def find_many_by_ids(cls, ids: Sequence[int]) -> Sequence[Self]:
        return await cls.find_many({'_id': {'$in': ids}})

    async def find_many_nearby_users(
            self, *,
            radius_meters: float = NEARBY_USERS_RADIUS_METERS,
            limit: int = NEARBY_USERS_LIMIT) -> Sequence[Self]:
        if not self.home_point:
            return []

        # results are already sorted by distance
        return await self.find_many({
            'home_point': {'$nearSphere': {
                '$geometry': self.home_point,
                '$maxDistance': radius_meters,
            }},
        }, limit=limit)

    async def distance_to(self, point: Point | None) -> float | None:
        return haversine_distance(self.home_point, point) if self.home_point and point else None
