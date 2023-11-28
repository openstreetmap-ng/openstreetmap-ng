from collections.abc import Awaitable, Callable
from datetime import timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import load_only

from db import DB
from lib.crypto import HASH_SIZE, hash_b
from models.db.cache_entry import CacheEntry
from utils import utcnow

# NOTE: ideally we would use Redis for caching, but for now this will be good enough

CACHE_HASH_SIZE = HASH_SIZE

_DEFAULT_CACHE_EXPIRE = timedelta(days=3)


def _hash_key(key: str, context: str) -> bytes:
    return hash_b(key, context=context)


class Cache:
    @staticmethod
    async def get_one_by_id(cache_id: bytes, factory: Callable[[], Awaitable[str]]) -> str:
        """
        Get a value from the cache by ID.

        If the value is not in the cache, call the async factory to generate it.
        """

        async with DB() as session:
            entry = await session.get(CacheEntry, cache_id, options=[load_only(CacheEntry.value, raiseload=True)])
            if not entry:
                value = await factory()
                entry = CacheEntry(
                    id=cache_id,
                    value=value,
                    expires_at=utcnow() + _DEFAULT_CACHE_EXPIRE,
                )
                stmt = insert(CacheEntry).values(entry).on_conflict_do_nothing(index_elements=[CacheEntry.id])
                await session.execute(stmt)
            return entry.value

    @staticmethod
    async def get_one_by_key(key: str, context: str, factory: Callable[[], Awaitable[str]]) -> str:
        """
        Get a value from the cache by key string.

        Context is used to namespace the cache and prevent collisions.

        If the value is not in the cache, call the async factory to generate it.
        """

        return await Cache.get_one_by_id(_hash_key(key, context), factory)
