from abc import ABC
from datetime import timedelta
from typing import Awaitable, Callable

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import load_only

from db import DB
from lib.crypto import hash_b
from models.db.cache_entry import CacheEntry
from utils import utcnow

# NOTE: ideally we would use Redis for caching, but for now this will be good enough

_DEFAULT_CACHE_EXPIRE = timedelta(days=3)

# we use a prefix to avoid key/value hash collisions
# which could be crafted easily by an attacker
_HASH_KEY_PREFIX = b'\x00'
_HASH_VALUE_PREFIX = b'\x01'


def _hash_key(key: str) -> bytes:
    return _HASH_KEY_PREFIX + hash_b(key, context=None)


def _hash_value(value: str) -> bytes:
    return _HASH_VALUE_PREFIX + hash_b(value, context=None)


class Cache(ABC):
    @staticmethod
    async def _get_one_by_id(cache_id: bytes, factory: Callable[[], Awaitable[str]]) -> str:
        async with DB() as session:
            entry = await session.get(CacheEntry, cache_id, options=[load_only(CacheEntry.value)])
            if not entry:
                value = await factory()
                entry = CacheEntry(
                    id=cache_id,
                    value=value,
                    expires_at=utcnow() + _DEFAULT_CACHE_EXPIRE)
                stmt = insert(CacheEntry) \
                    .values(entry)\
                    .on_conflict_do_nothing(
                        index_elements=[CacheEntry.id])
                await session.execute(stmt)
            return entry.value

    @ staticmethod
    async def get_one_by_key(key: str, factory: Callable[[], Awaitable[str]]) -> str:
        return await Cache._get_one_by_id(_hash_key(key), factory)

    @ staticmethod
    async def get_one_by_value(value: str, factory: Callable[[], Awaitable[str]]) -> str:
        return await Cache._get_one_by_id(_hash_value(value), factory)
