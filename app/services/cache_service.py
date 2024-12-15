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
)

CacheContext = NewType('CacheContext', str)

__all__ = ('CacheContext',)

_COMPRESS = ZstdCompressor(
    level=CACHE_COMPRESS_ZSTD_LEVEL, threads=CACHE_COMPRESS_ZSTD_THREADS, write_checksum=False
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
        """
        if hash_key:
            cache_id = hash_bytes(key)
        elif isinstance(key, str):
            cache_id = key.encode()
        else:
            cache_id = key

        cache_key = f'{context}:{cache_id.hex()}'

        async with valkey() as conn:
            value_stored: bytes | None = await conn.get(cache_key)

            if value_stored is not None:
                # on cache hit, decompress the value if needed (first byte is compression marker)
                if value_stored[0] == 0xFF:
                    value = _DECOMPRESS(value_stored[1:], allow_extra_data=False)
                else:
                    value = value_stored[1:]

            else:
                # on cache miss, call the factory to generate the value and cache it
                value = await factory()

                if not isinstance(value, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
                    raise TypeError(f'Cache factory returned {type(value)!r}, expected bytes')

                if len(value) >= CACHE_COMPRESS_MIN_SIZE:
                    logging.debug('Compressing cache %r value of size %s', cache_key, sizestr(len(value)))
                    value_stored = b'\xff' + _COMPRESS(value)
                else:
                    value_stored = b'\x00' + value

                await conn.set(cache_key, value_stored, ex=ttl, nx=True)

        return CacheEntry(id=cache_id, value=value)
