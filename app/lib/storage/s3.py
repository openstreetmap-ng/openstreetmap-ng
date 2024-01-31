import aioboto3

from app.lib.file_cache import FileCache
from app.lib.storage.base import StorageBase
from app.limits import S3_CACHE_EXPIRE

_s3 = aioboto3.Session()


class S3Storage(StorageBase):
    """
    File storage based on AWS S3.

    Uses FileCache for local caching.
    """

    __slots__ = ('_context', '_fc')

    def __init__(self, context: str):
        super().__init__(context)
        self._fc = FileCache(context)

    async def load(self, key: str) -> bytes:
        if (data := await self._fc.get(key)) is not None:
            return data

        async with _s3.client('s3') as s3:
            data = await (await s3.get_object(Bucket=self._context, Key=key))['Body'].read()

        await self._fc.set(key, data, ttl=S3_CACHE_EXPIRE)
        return data

    async def save(self, data: bytes, suffix: str, *, random: bool = True) -> str:
        key = self._make_key(data, suffix, random)

        async with _s3.client('s3') as s3:
            await s3.put_object(Bucket=self._context, Key=key, Body=data)

        return key

    async def delete(self, key: str) -> None:
        async with _s3.client('s3') as s3:
            await s3.delete_object(Bucket=self._context, Key=key)

        await self._fc.delete(key)
