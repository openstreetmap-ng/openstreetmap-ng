import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import NamedTuple, NewType

from sizestr import sizestr
from zstandard import ZstdCompressor, ZstdDecompressor

from app.db import valkey
from app.lib.crypto import hash_bytes
from app.limits import (
    CACHE_COMPRESS_MIN_SIZE,
    CACHE_COMPRESS_ZSTD_LEVEL,
    CACHE_COMPRESS_ZSTD_THREADS,
    CACHE_DEFAULT_EXPIRE,
    CACHE_WRITE_LOCK_TIMEOUT,
)

CacheContext = NewType('CacheContext', str)

_COMPRESS = ZstdCompressor(
    level=CACHE_COMPRESS_ZSTD_LEVEL,
    threads=CACHE_COMPRESS_ZSTD_THREADS,
    write_checksum=False,
).compress

_DECOMPRESS = ZstdDecompressor().decompress


class CacheEntry(NamedTuple):
    id: bytes
    value: bytes


class CacheService:
    @staticmethod
    async def get(
        key: str | bytes,
        context: CacheContext,
        factory: Callable[[], Awaitable[bytes]],
        *,
        hash_key: bool = False,
        ttl: timedelta = CACHE_DEFAULT_EXPIRE,
    ) -> CacheEntry:
        """
        Get a value from the cache.
        If the value is not in the cache, call the async factory to obtain it.
        Uses a simple locking mechanism to prevent duplicate generation.
        """
        cache_id = (
            hash_bytes(key)
            if hash_key  #
            else (key.encode() if isinstance(key, str) else key)
        )
        cache_key = f'{context}:{cache_id.hex()}'

        async with valkey() as conn:
            # Try to get the cached value first
            value_stored: bytes | None = await conn.get(cache_key)
            if value_stored is not None:
                value = (
                    _DECOMPRESS(value_stored[1:])
                    if value_stored[0] == 0xFF  #
                    else value_stored[1:]
                )
                return CacheEntry(cache_id, value)

            # On cache miss, check if someone else is already generating
            lock_key = f'lock:{cache_key}'
            lock_acquired = await conn.set(lock_key, b'', ex=CACHE_WRITE_LOCK_TIMEOUT, nx=True)

            if not lock_acquired:
                # Someone else is generating the value, wait briefly then try again
                await asyncio.sleep(0.1)
                return await CacheService.get(cache_id, context, factory, ttl=ttl)

            try:
                # We have the lock, generate the value
                value = await factory()

                # Compress if needed
                if len(value) >= CACHE_COMPRESS_MIN_SIZE:
                    logging.debug('Compressing cache %r value of size %s', cache_key, sizestr(len(value)))
                    value_stored = b'\xff' + _COMPRESS(value)
                else:
                    value_stored = b'\x00' + value

                # Store and return the value
                await conn.set(cache_key, value_stored, ex=ttl)
                return CacheEntry(cache_id, value)

            finally:
                # Release the lock
                await conn.delete(lock_key)
