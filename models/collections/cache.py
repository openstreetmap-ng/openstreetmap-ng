from datetime import datetime, timedelta
from typing import Annotated, Self

from pydantic import Field

from lib.crypto import hash_hex
from models.collections.base import Base
from models.str import HexStr
from utils import utcnow

# NOTE: ideally we would use Redis for caching, but for now this will be good enough

_DEFAULT_CACHE_EXPIRE = timedelta(days=3)

# we use a prefix to avoid key/value hash collisions
# which could be crafted easily by an attacker
_HASH_KEY_PREFIX = '00'
_HASH_VALUE_PREFIX = '01'


class Cache(Base):
    id: Annotated[HexStr, Field(alias='_id', frozen=True)]
    expires_at: datetime
    value: Annotated[str, Field(frozen=True)]

    @staticmethod
    def hash_key(key: str) -> str:
        return _HASH_KEY_PREFIX + hash_hex(key, context=None)

    @staticmethod
    def hash_value(value: str) -> str:
        return _HASH_VALUE_PREFIX + hash_hex(value, context=None)

    @classmethod
    async def create_from_key(cls, key: str, value: str, ttl: timedelta = _DEFAULT_CACHE_EXPIRE) -> Self:
        id_ = Cache.hash_key(key)
        return await cls._create(id_, value, ttl)

    @classmethod
    async def create_from_key_id(cls, id_: str, value: str, ttl: timedelta = _DEFAULT_CACHE_EXPIRE) -> Self:
        return await cls._create(id_, value, ttl)

    @classmethod
    async def create_from_value(cls, value: str, ttl: timedelta = _DEFAULT_CACHE_EXPIRE) -> Self:
        id_ = Cache.hash_value(value)
        return await cls._create(id_, value, ttl)

    @classmethod
    async def _create(cls, id_: str, value: str, ttl: timedelta) -> Self:
        while True:
            cache = cls(id=id_, expires_at=utcnow() + ttl, value=value)
            try:
                await cache.create()
                return cache
            except Exception:
                # TODO: specify exception, logging
                return cls.get_one_by_id(id_)
