from collections.abc import Awaitable, Callable
from datetime import timedelta

from app.db import redis
from app.lib.crypto import hash_bytes
from app.limits import CACHE_DEFAULT_EXPIRE
from app.models.cache_entry import CacheEntry


class CacheService:
    @staticmethod
    async def get_one_by_cache_id(
        cache_id: bytes,
        context: str,
        factory: Callable[[], Awaitable[str | bytes]],
        *,
        ttl: timedelta = CACHE_DEFAULT_EXPIRE,
    ) -> CacheEntry:
        """
        Get a value from the cache by id.

        If the value is not in the cache, call the async factory to generate it.
        """

        redis_key = f'{context}:{cache_id.hex()}'

        async with redis() as conn:
            value: bytes | None = await conn.get(redis_key)

            # on cache miss, call the factory to generate the value and cache it
            if value is None:
                value_maybe_str: str | bytes = await factory()
                await conn.set(redis_key, value_maybe_str, ex=ttl, nx=True)
                value = value_maybe_str.encode() if isinstance(value_maybe_str, str) else value_maybe_str

        return CacheEntry(id=cache_id, value=value)

    @staticmethod
    async def get_one_by_key(
        key: str,
        context: str,
        factory: Callable[[], Awaitable[str | bytes]],
        *,
        ttl: timedelta = CACHE_DEFAULT_EXPIRE,
    ) -> CacheEntry:
        """
        Get a value from the cache by key string.

        Context is used to namespace the cache and prevent collisions.

        If the value is not in the cache, call the async factory to generate it.
        """

        cache_id = hash_bytes(key, context=None)

        return await CacheService.get_one_by_cache_id(cache_id, context, factory, ttl=ttl)
