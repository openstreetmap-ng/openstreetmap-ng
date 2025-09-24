import fcntl
import logging
from asyncio import get_running_loop, timeout
from collections import OrderedDict
from datetime import timedelta
from io import FileIO
from os import stat
from pathlib import Path
from time import time
from typing import NamedTuple

from google.protobuf.message import DecodeError
from sizestr import sizestr

from app.config import (
    FILE_CACHE_DIR,
    FILE_CACHE_LOCK_TIMEOUT,
    FILE_CACHE_MEMORY_MAX_ENTRIES,
    FILE_CACHE_MEMORY_MAX_VALUE_SIZE,
    FILE_CACHE_SIZE,
)
from app.models.proto.server_pb2 import FileCacheMeta
from app.models.types import StorageKey


class _CleanupInfo(NamedTuple):
    expires_at: int | float
    size: int
    path: Path


class _MemoryEntry(NamedTuple):
    expires_at: int | None
    data: bytes
    mtime: float


_MEMORY_CACHES: dict[Path, OrderedDict[str, _MemoryEntry]] = {}


class _FileCacheLock:
    """A process-safe lock for file cache operations"""

    __slots__ = ('_file', 'key', 'path')

    def __init__(self, path: Path, key: StorageKey):
        self.path = path
        self.key = key
        self._file: FileIO | None = None

    async def __aenter__(self) -> '_FileCacheLock':
        dir = self.path.parent
        dir.mkdir(parents=True, exist_ok=True)
        lock_path = dir.joinpath(f'.{self.path.name}.lock')
        lock_file = self._file = lock_path.open('wb', buffering=0)

        async with timeout(FILE_CACHE_LOCK_TIMEOUT.total_seconds()):
            loop = get_running_loop()
            await loop.run_in_executor(
                None, lambda: fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._file is not None:
            self._file.close()
            self._file = None


class FileCache:
    __slots__ = ('_base_dir', '_memory_cache')

    def __init__(self, dirname: str, *, cache_dir: Path = FILE_CACHE_DIR):
        self._base_dir = cache_dir.joinpath(dirname)
        self._memory_cache = _MEMORY_CACHES.setdefault(self._base_dir, OrderedDict())

    async def get(self, key: StorageKey) -> bytes | None:
        """
        Get a value from the file cache by key string.
        Returns None if the cache is not found.
        """
        path = self._get_path(key)
        mentry = self._memory_cache.get(key)
        if mentry is not None:
            try:
                if (
                    mentry.expires_at is None or mentry.expires_at > time()
                ) and path.stat().st_mtime == mentry.mtime:
                    logging.debug('Cache hit for %r (memory)', key)
                    self._memory_cache.move_to_end(key)
                    return mentry.data
            except OSError:
                pass

            self._memory_cache.pop(key)

        try:
            with path.open('rb') as f:
                loop = get_running_loop()
                entry_bytes = await loop.run_in_executor(None, f.read)
                entry_mtime = stat(f.fileno()).st_mtime  # noqa: PTH116
            entry = FileCacheMeta.FromString(entry_bytes)
        except (OSError, DecodeError):
            logging.debug('Cache read error for %r', key)
            return None

        # If set, check TTL expiration
        if entry.HasField('expires_at'):
            expires_at = entry.expires_at
            if expires_at <= time():
                logging.debug('Cache miss for %r', key)
                path.unlink(missing_ok=True)
                return None
        else:
            expires_at = None

        if not entry.volatile and len(entry.data) <= FILE_CACHE_MEMORY_MAX_VALUE_SIZE:
            self._memory_cache[key] = _MemoryEntry(expires_at, entry.data, entry_mtime)
            if len(self._memory_cache) > FILE_CACHE_MEMORY_MAX_ENTRIES:
                self._memory_cache.popitem(False)

        logging.debug('Cache hit for %r (disk)', key)
        return entry.data

    def lock(self, key: StorageKey) -> _FileCacheLock:
        """Get a write lock for the given key."""
        return _FileCacheLock(self._get_path(key), key)

    async def set(
        self,
        lock: _FileCacheLock,
        data: bytes,
        *,
        ttl: timedelta | None,
        volatile: bool = False,
    ) -> None:
        """Set a value in the file cache."""
        expires_at = int(time() + ttl.total_seconds()) if ttl is not None else None
        entry = FileCacheMeta(data=data, expires_at=expires_at, volatile=volatile)
        entry_bytes = entry.SerializeToString()

        path = lock.path
        temp_path = path.parent.joinpath(f'.{path.name}.tmp')
        with temp_path.open('wb', buffering=0) as f:
            loop = get_running_loop()
            await loop.run_in_executor(None, f.write, entry_bytes)
            mtime = stat(f.fileno()).st_mtime  # noqa: PTH116
        temp_path.replace(path)

        # Populate memory cache after successful write so mtime is accurate
        if not volatile and len(data) <= FILE_CACHE_MEMORY_MAX_VALUE_SIZE:
            self._memory_cache[lock.key] = _MemoryEntry(expires_at, data, mtime)
            self._memory_cache.move_to_end(lock.key)
            if len(self._memory_cache) > FILE_CACHE_MEMORY_MAX_ENTRIES:
                self._memory_cache.popitem(False)

    def delete(self, key: StorageKey) -> None:
        """Delete a key from the file cache."""
        path = self._get_path(key)
        path.unlink(missing_ok=True)
        self._memory_cache.pop(key, None)

    # TODO: runner, with lock
    # TODO: cleanup orphaned locks and temps
    async def cleanup(self):
        """Cleanup the file cache, removing stale entries."""
        infos: list[_CleanupInfo] = []
        total_size = 0
        now = time()

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

            size = len(entry_bytes)
            infos.append(_CleanupInfo(expires_at, size, path))
            total_size += size

        logging.debug(
            'File cache usage is %s of %s',
            sizestr(total_size),
            sizestr(FILE_CACHE_SIZE),
        )
        if total_size <= FILE_CACHE_SIZE:
            return

        # prioritize cleanup of entries closer to expiration (iterating in reverse)
        infos.sort(key=lambda ci: ci.expires_at, reverse=True)

        while total_size > FILE_CACHE_SIZE:
            info = infos.pop()
            key = info.path.name
            logging.debug('Cache cleanup for %r (reason: size)', key)
            info.path.unlink(missing_ok=True)
            total_size -= info.size

    def _get_path(self, key: StorageKey, /):
        """Get the path to a file in the cache."""
        return (
            self._base_dir.joinpath(key[:2], key[2:4], key)
            if len(key) > 4
            else self._base_dir.joinpath(key)
        )
