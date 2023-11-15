import logging

from anyio import Path

from config import FILE_CACHE_DIR


class FileCache:
    _base_dir: Path

    def __init__(self, context: str, *, cache_dir: Path = FILE_CACHE_DIR):
        self._base_dir = cache_dir / context

    async def _get_path(self, key: str) -> Path:
        if len(key) < 3:
            raise ValueError('key must be at least 3 characters long')

        d1 = key[:1]
        d2 = key[1:3]
        dir_path = self._base_dir / d1 / d2
        await dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path / key

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
