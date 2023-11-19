import logging
import string

from anyio import Path

from config import FILE_CACHE_DIR

_FILE_WHITELIST_CHARS = set(string.ascii_letters + string.digits + '._- ')


class FileCache:
    _base_dir: Path
    _base_dir_resolved: Path | None

    def __init__(self, context: str, *, cache_dir: Path = FILE_CACHE_DIR):
        self._base_dir = cache_dir / context
        self._base_dir_resolved = None

    async def _get_path(self, key: str) -> Path:
        """
        Get the path to a file in the file cache by key string.

        >>> await FileCache('context')._get_path('file_key')
        Path('.../context/f/il/file_key')
        """

        if len(key) < 3:
            raise ValueError('key must be at least 3 characters long')

        if not all(c in _FILE_WHITELIST_CHARS for c in key):
            raise ValueError('key contains invalid characters')

        d1 = key[:1]
        d2 = key[1:3]

        if '.' in d1 or '.' in d2:
            raise ValueError('key cannot start with a dot')

        dir_path = self._base_dir / d1 / d2
        full_path = dir_path / key
        full_path = await full_path.resolve()

        if self._base_dir_resolved is None:
            self._base_dir_resolved = await self._base_dir.resolve()

        if not full_path.is_relative_to(self._base_dir_resolved):
            raise ValueError('key is invalid')

        await dir_path.mkdir(parents=True, exist_ok=True)
        return full_path

    async def get(self, key: str) -> bytes | None:
        """
        Get a value from the file cache by key string.
        """

        path = await self._get_path(key)

        try:
            return await path.read_bytes()
        except OSError:
            return None

    # TODO: TTL Support
    async def set(self, key: str, data: bytes) -> None:  # noqa: A003
        """
        Set a value in the file cache by key string.
        """

        path = await self._get_path(key)

        try:
            async with await path.open('xb') as f:
                await f.write(data)
        except OSError:
            if not await path.is_file():
                logging.warning('Failed to create file cache %r', path)
                raise

    async def delete(self, key: str) -> None:
        """
        Delete a key from the file cache.
        """

        path = await self._get_path(key)

        await path.unlink(missing_ok=True)

    async def cleanup(self):
        """
        Cleanup the file cache, removing stale entries.
        """

        # TODO: implement cleaning logic here, using Lock for distributed-process safety
        ...
