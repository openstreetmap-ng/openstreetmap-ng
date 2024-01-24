from collections.abc import Awaitable, Callable
from datetime import timedelta

from app.db import redis
from app.lib.crypto import hash_bytes
from app.limits import CACHE_DEFAULT_EXPIRE
from app.models.cache_entry import CacheEntry

# NOTE: ideally we would use Redis for caching, but for now this will be good enough


def _hash_key(key: str, context: str) -> bytes:
    return hash_bytes(key, context=context)


class CacheService:
    @staticmethod
    async def get_one_by_id(
        cache_id: bytes,
        factory: Callable[[], Awaitable[str]],
        *,
        ttl: timedelta = CACHE_DEFAULT_EXPIRE,
    ) -> CacheEntry:
        """
        Get a value from the cache by id.

        If the value is not in the cache, call the async factory to generate it.
        """

        cache_id_str = cache_id.hex()

        async with redis() as conn:
            value: str | None = await conn.get(cache_id_str)

            if value is None:
                value = await factory()
                await conn.set(cache_id_str, value, ex=ttl.total_seconds(), nx=True)

        return CacheEntry(id=cache_id, value=value)

    @staticmethod
    async def get_one_by_key(
        key: str,
        context: str,
        factory: Callable[[], Awaitable[str]],
        *,
        ttl: timedelta = CACHE_DEFAULT_EXPIRE,
    ) -> CacheEntry:
        """
        Get a value from the cache by key string.

        Context is used to namespace the cache and prevent collisions.

        If the value is not in the cache, call the async factory to generate it.
        """

        cache_id = _hash_key(key, context)

        return await CacheService.get_one_by_id(cache_id, factory, ttl=ttl)
