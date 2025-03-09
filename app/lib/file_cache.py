import fcntl
import logging
import time
from asyncio import get_running_loop, timeout
from datetime import timedelta
from io import BufferedWriter
from pathlib import Path
from typing import NamedTuple

import cython
from google.protobuf.message import DecodeError
from sizestr import sizestr

from app.config import FILE_CACHE_DIR, FILE_CACHE_SIZE_GB
from app.limits import FILE_CACHE_LOCK_TIMEOUT
from app.models.proto.server_pb2 import FileCacheMeta
from app.models.types import StorageKey


class _CleanupInfo(NamedTuple):
    expires_at: int | float
    size: int
    path: Path


class _FileCacheLock:
    """A process-safe lock for file cache operations"""

    __slots__ = ('_file', 'path')

    def __init__(self, path: Path):
        self.path = path
        self._file: BufferedWriter | None = None

    async def __aenter__(self) -> '_FileCacheLock':
        dir = self.path.parent
        dir.mkdir(parents=True, exist_ok=True)
        lock_path = dir.joinpath(f'.{self.path.name}.lock')
        lock_file = self._file = lock_path.open('wb')

        async with timeout(FILE_CACHE_LOCK_TIMEOUT.total_seconds()):
            loop = get_running_loop()
            await loop.run_in_executor(None, lambda: fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX))

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._file is not None:
            self._file.close()
            self._file = None


class FileCache:
    __slots__ = ('_base_dir',)

    def __init__(self, dirname: str, *, cache_dir: Path = FILE_CACHE_DIR):
        self._base_dir = cache_dir.joinpath(dirname)

    async def get(self, key: StorageKey) -> bytes | None:
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

        # If set, check TTL expiration
        if entry.HasField('expires_at') and entry.expires_at < time.time():
            logging.debug('Cache miss for %r', key)
            path.unlink(missing_ok=True)
            return None

        logging.debug('Cache hit for %r', key)
        return entry.data

    def lock(self, key: StorageKey) -> _FileCacheLock:
        """Get a write lock for the given key."""
        return _FileCacheLock(_get_path(self._base_dir, key))

    @staticmethod
    async def set(lock: _FileCacheLock, data: bytes, *, ttl: timedelta | None) -> None:
        """Set a value in the file cache."""
        expires_at = int(time.time() + ttl.total_seconds()) if (ttl is not None) else None
        entry = FileCacheMeta(data=data, expires_at=expires_at)
        entry_bytes = entry.SerializeToString()

        path = lock.path
        temp_path = path.parent.joinpath(f'.{path.name}.tmp')
        with temp_path.open('wb') as f:
            loop = get_running_loop()
            await loop.run_in_executor(None, f.write, entry_bytes)
        temp_path.rename(path)

    def delete(self, key: StorageKey) -> None:
        """Delete a key from the file cache."""
        path = _get_path(self._base_dir, key)
        path.unlink(missing_ok=True)

    # TODO: runner, with lock
    # TODO: cleanup orphaned locks and temps
    async def cleanup(self):
        """Cleanup the file cache, removing stale entries."""
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
        infos.sort(key=lambda ci: ci.expires_at, reverse=True)

        while total_size > limit_size:
            info = infos.pop()
            key = info.path.name
            logging.debug('Cache cleanup for %r (reason: size)', key)
            info.path.unlink(missing_ok=True)
            total_size -= info.size


@cython.cfunc
def _get_path(base_dir: Path, key: StorageKey, /) -> Path:
    """Get the path to a file in the cache."""
    return base_dir.joinpath(key[:2], key[2:4], key) if len(key) > 4 else base_dir.joinpath(key)
