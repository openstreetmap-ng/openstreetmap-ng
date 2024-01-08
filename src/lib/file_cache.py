import logging

from anyio import Path

from src.config import FILE_CACHE_DIR
from src.lib.crypto import hash_hex


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

        path = await self._get_path(key)

        try:
            result = await path.read_bytes()
            logging.debug('Cache hit for %r', key)
            return result
        except OSError:
            logging.debug('Cache miss for %r', key)
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
