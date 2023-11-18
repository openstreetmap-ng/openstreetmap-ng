from config import FILE_DATA_DIR
from lib.file_cache import FileCache
from lib.storage.base import StorageBase


class LocalStorage(StorageBase):
    """
    File storage based on FileCache.
    """

    def __init__(self, context: str):
        super().__init__(context)
        self._fc = FileCache(context, cache_dir=FILE_DATA_DIR)

    async def load(self, key: str) -> bytes:
        result = await self._fc.get(key)
        if result is None:
            raise FileNotFoundError(key)
        return result

    async def save(self, data: bytes, suffix: str, *, random: bool = True) -> str:
        key = self._get_key(data, suffix, random)
        await self._fc.set(key, data)

    async def delete(self, key: str) -> None:
        await self._fc.delete(key)
