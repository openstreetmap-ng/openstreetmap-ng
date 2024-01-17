import logging
import time
from datetime import timedelta

import cython
from anyio import Path

from app.config import FILE_CACHE_DIR
from app.lib_cython.crypto import hash_hex
from app.models.msgspec.file_cache_entry import FileCacheEntry

if cython.compiled:
    print(f'{__name__}: 🐇 compiled')


class FileCache:
    _base_dir: Path

    def __init__(self, context: str, *, cache_dir: Path = FILE_CACHE_DIR):
        self._base_dir = cache_dir / context

    async def _get_path(self, key_str: str) -> Path:
        """
        Get the path to a file in the file cache by key string.

        >>> await FileCache('context')._get_path('file_key')
        Path('.../context/4/68/468e5f...')
        """

        key: str = hash_hex(key_str)

        d1 = key[:1]
        d2 = key[1:3]

        dir_path = self._base_dir / d1 / d2
        await dir_path.mkdir(parents=True, exist_ok=True)

        full_path = dir_path / key
        return full_path

    async def get(self, key: str) -> bytes | None:
        """
        Get a value from the file cache by key string.
        """

        path = await self.get_path(key)

        try:
            entry_bytes = await path.read_bytes()
        except OSError:
            logging.debug('Cache miss for %r', key)
            return None

        entry = FileCacheEntry.from_bytes(entry_bytes)

        if entry.expires_at and entry.expires_at < int(time.time()):
            logging.debug('Cache miss for %r', key)
            await path.unlink(missing_ok=True)
            return None

        logging.debug('Cache hit for %r', key)
        return entry.data

    async def set(self, key: str, data: bytes, *, ttl: timedelta | None) -> None:  # noqa: A003
        """
        Set a value in the file cache by key string.
        """

        path = await self.get_path(key)
        expires_at = int(time.time()) + ttl.total_seconds() if ttl else None
        entry = FileCacheEntry(expires_at, data)
        entry_bytes = entry.to_bytes()

        try:
            async with await path.open('xb') as f:
                await f.write(entry_bytes)
        except OSError:
            if not await path.is_file():
                logging.warning('Failed to create file cache %r', path)
                raise

    async def delete(self, key: str) -> None:
        """
        Delete a key from the file cache.
        """

        path = await self.get_path(key)

        await path.unlink(missing_ok=True)

    async def cleanup(self):
        """
        Cleanup the file cache, removing stale entries.
        """

        # TODO: implement cleaning logic here, using Lock for distributed-process safety
        ...
