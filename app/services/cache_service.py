import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta

from zstandard import ZstdCompressor, ZstdDecompressor

from app.db import redis
from app.lib.crypto import hash_bytes
from app.lib.naturalsize import naturalsize
from app.limits import (
    CACHE_COMPRESS_MIN_SIZE,
    CACHE_COMPRESS_ZSTD_LEVEL,
    CACHE_COMPRESS_ZSTD_THREADS,
    CACHE_DEFAULT_EXPIRE,
)
from app.models.cache_entry import CacheEntry

_compress = ZstdCompressor(
    level=CACHE_COMPRESS_ZSTD_LEVEL,
    threads=CACHE_COMPRESS_ZSTD_THREADS,
).compress

_decompress = ZstdDecompressor().decompress


class CacheService:
    @staticmethod
    async def get_one_by_cache_id(
        cache_id: bytes,
        context: str,
        factory: Callable[[], Awaitable[bytes]],
        *,
        ttl: timedelta = CACHE_DEFAULT_EXPIRE,
    ) -> CacheEntry:
        """
        Get a value from the cache by id.

        If the value is not in the cache, call the async factory to generate it.
        """

        redis_key = f'{context}:{cache_id.hex()}'

        async with redis() as conn:
            value_stored: bytes | None = await conn.get(redis_key)

            if value_stored is not None:
                # on cache hit, decompress the value if needed (first byte is compression marker)
                if value_stored[0] == '\xff':
                    value = _decompress(value_stored[1:], allow_extra_data=False)
                else:
                    value = value_stored[1:]

            else:
                # on cache miss, call the factory to generate the value and cache it
                value = await factory()

                if not isinstance(value, bytes):
                    raise TypeError(f'Cache factory returned {type(value)!r}, expected bytes')

                value_len = len(value)
                if value_len >= CACHE_COMPRESS_MIN_SIZE:
                    logging.debug('Compressing cache %r value of size %s', redis_key, naturalsize(value_len))
                    value_stored = b'\xff' + _compress(value)
                else:
                    value_stored = b'\x00' + value

                await conn.set(redis_key, value_stored, ex=ttl, nx=True)

        return CacheEntry(id=cache_id, value=value)

    @staticmethod
    async def get_one_by_key(
        key: str,
        context: str,
        factory: Callable[[], Awaitable[bytes]],
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
