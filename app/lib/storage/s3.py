from typing import override

import aioboto3

from app.lib.buffered_random import buffered_rand_storage_key
from app.lib.storage.base import StorageBase
from app.limits import S3_CACHE_EXPIRE
from app.models.types import StorageKey
from app.services.cache_service import CacheContext, CacheService

_S3 = aioboto3.Session()


class S3Storage(StorageBase):
    """File storage based on AWS S3 and local cache."""

    __slots__ = ('_bucket', '_context')

    def __init__(self, bucket: str):
        super().__init__()
        self._bucket = bucket
        self._context = CacheContext(f'S3_{bucket}')

    @override
    async def load(self, key: StorageKey) -> bytes:
        async def factory() -> bytes:
            async with _S3.client('s3') as s3:
                return await (await s3.get_object(Bucket=self._bucket, Key=key))['Body'].read()

        return await CacheService.get(
            key,
            context=self._context,
            factory=factory,
            ttl=S3_CACHE_EXPIRE,
        )

    @override
    async def save(self, data: bytes, suffix: str) -> StorageKey:
        key = buffered_rand_storage_key(suffix)

        async with _S3.client('s3') as s3:
            await s3.put_object(Bucket=self._bucket, Key=key, Body=data)

        return key

    @override
    async def delete(self, key: StorageKey) -> None:
        async with _S3.client('s3') as s3:
            await s3.delete_object(Bucket=self._bucket, Key=key)

        CacheService.delete(self._context, key)
