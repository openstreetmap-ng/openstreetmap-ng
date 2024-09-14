import logging
import time
from asyncio import get_running_loop
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from google.protobuf.message import DecodeError
from sizestr import sizestr

from app.config import FILE_CACHE_DIR, FILE_CACHE_SIZE_GB
from app.lib.buffered_random import buffered_randbytes
from app.lib.crypto import hash_hex
from app.models.messages_pb2 import FileCacheMeta


class _CleanupInfo(NamedTuple):
    expires_at: int | float
    size: int
    path: Path


class FileCache:
    __slots__ = ('_base_dir',)

    def __init__(self, context: str, *, cache_dir: Path = FILE_CACHE_DIR):
        self._base_dir: Path = cache_dir.joinpath(context)

    async def get(self, key: str) -> bytes | None:
        """
        Get a value from the file cache by key string.

        Returns None if the cache is not found.
        """
        path = _get_path(self._base_dir, key)

        try:
            loop = get_running_loop()
            entry_bytes = await loop.run_in_executor(None, path.read_bytes)
            entry = FileCacheMeta.FromString(entry_bytes)
        except (OSError, DecodeError):
            logging.debug('Cache read error for %r', key)
            return None

        # if provided, check time-to-live
        if entry.HasField('expires_at') and entry.expires_at < time.time():
            logging.debug('Cache miss for %r', key)
            path.unlink(missing_ok=True)
            return None

        logging.debug('Cache hit for %r', key)
        return entry.data

    async def set(self, key: str, data: bytes, *, ttl: timedelta | None) -> None:
        """
        Set a value in the file cache by key string.
        """
        path = _get_path(self._base_dir, key)
        path.parent.mkdir(parents=True, exist_ok=True)

        expires_at = int(time.time() + ttl.total_seconds()) if (ttl is not None) else None
        entry = FileCacheMeta(data=data, expires_at=expires_at)
        entry_bytes = entry.SerializeToString()

        temp_name = f'.{buffered_randbytes(16).hex()}.tmp'
        temp_path = path.with_name(temp_name)

        with temp_path.open('xb') as f:
            loop = get_running_loop()
            await loop.run_in_executor(None, f.write, entry_bytes)

        temp_path.rename(path)

    def delete(self, key: str) -> None:
        """
        Delete a key from the file cache.
        """
        path = _get_path(self._base_dir, key)
        path.unlink(missing_ok=True)

    # TODO: runner, with lock
    async def cleanup(self):
        """
        Cleanup the file cache, removing stale entries.
        """
        infos: list[_CleanupInfo] = []
        total_size: int = 0
        limit_size: int = FILE_CACHE_SIZE_GB * 1024 * 1024 * 1024
        now = time.time()

        for path in self._base_dir.rglob('*'):
            key = path.name

            try:
                loop = get_running_loop()
                entry_bytes = await loop.run_in_executor(None, path.read_bytes)
                entry = FileCacheMeta.FromString(entry_bytes)
            except (OSError, DecodeError):
                logging.debug('Cache read error for %r', key)
                continue

            if entry.HasField('expires_at'):
                if entry.expires_at < now:
                    logging.debug('Cache cleanup for %r (reason: time)', key)
                    path.unlink(missing_ok=True)
                    continue
                expires_at = entry.expires_at
            else:
                expires_at = float('inf')

            size = path.stat().st_size
            infos.append(_CleanupInfo(expires_at, size, path))
            total_size += size

        logging.debug('File cache usage is %s of %s', sizestr(total_size), sizestr(limit_size))
        if total_size <= limit_size:
            return

        # prioritize cleanup of entries closer to expiration (iterating in reverse)
        infos.sort(key=lambda info: info.expires_at, reverse=True)

        while total_size > limit_size:
            info = infos.pop()
            key = info.path.name
            logging.debug('Cache cleanup for %r (reason: size)', key)
            info.path.unlink(missing_ok=True)
            total_size -= info.size


@lru_cache(maxsize=1024)
def _get_path(base_dir: Path, key_str: str) -> Path:
    """
    Get the path to a file in the file cache by key string.

    >>> _get_path(Path('context'), 'file_key')
    Path('.../context/46/8e/468e5f...')
    """
    key: str = hash_hex(key_str)
    return base_dir.joinpath(key[:2], key[2:4], key)
