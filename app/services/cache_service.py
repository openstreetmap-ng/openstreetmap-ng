from collections.abc import Awaitable, Callable
from datetime import timedelta
from inspect import isawaitable
from typing import NewType

import cython

from app.config import CACHE_DEFAULT_EXPIRE
from app.lib.file_cache import FileCache
from app.models.types import StorageKey

CacheContext = NewType('CacheContext', str)

_FactoryReturn = bytes | tuple[bytes, timedelta]


class CacheService:
    @staticmethod
    async def get(
        key: StorageKey,
        context: CacheContext,
        factory: Callable[[], Awaitable[_FactoryReturn] | _FactoryReturn],
        *,
        ttl: timedelta = CACHE_DEFAULT_EXPIRE,
        volatile: bool = False,
    ) -> bytes:
        """
        Get a value from the cache.
        If the value is not in the cache, call the async factory to obtain it.
        Uses a simple locking mechanism to prevent duplicate generation.
        """
        fc = _get_file_cache(context)

        # Try to get the cached value first
        value = await fc.get(key)
        if value is not None:
            return value

        # On cache miss, acquire a lock to prevent duplicate generation
        async with fc.lock(key) as lock:
            # Check again in case another process generated value while we were waiting
            value = await fc.get(key)
            if value is not None:
                return value

            # No one else has generated it, so we'll do it
            value = factory()
            if isawaitable(value):
                value = await value
            if isinstance(value, tuple):
                value, ttl = value

            await fc.set(lock, value, ttl=ttl, volatile=volatile)
            return value

    @staticmethod
    def delete(context: CacheContext, key: StorageKey) -> None:
        """Delete a key from the cache."""
        fc = _get_file_cache(context)
        fc.delete(key)


_FILE_CACHES: dict[CacheContext, FileCache] = {}


@cython.cfunc
def _get_file_cache(context: CacheContext):
    fc = _FILE_CACHES.get(context)
    if fc is None:
        fc = _FILE_CACHES[context] = FileCache(context)
    return fc
