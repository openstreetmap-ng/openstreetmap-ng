from typing import LiteralString, override

import aioboto3
from types_aiobotocore_s3.type_defs import PutObjectRequestTypeDef

from app.config import S3_CACHE_EXPIRE
from app.lib.storage.base import StorageBase
from app.models.types import StorageKey
from app.services.cache_service import CacheContext, CacheService
from speedup.buffered_rand import buffered_rand_storage_key

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
                return await (await s3.get_object(Bucket=self._bucket, Key=key))[
                    'Body'
                ].read()

        return await CacheService.get(
            key,
            context=self._context,
            factory=factory,
            ttl=S3_CACHE_EXPIRE,
        )

    @override
    async def save(
        self, data: bytes, suffix: LiteralString, metadata: dict[str, str] | None = None
    ) -> StorageKey:
        key = buffered_rand_storage_key(suffix)

        put_kwargs: PutObjectRequestTypeDef = {
            'Bucket': self._bucket,
            'Key': key,
            'Body': data,
        }

        if metadata is not None:
            put_kwargs['Metadata'] = metadata

        async with _S3.client('s3') as s3:
            await s3.put_object(**put_kwargs)

        return key

    @override
    async def delete(self, key: StorageKey) -> None:
        async with _S3.client('s3') as s3:
            await s3.delete_object(Bucket=self._bucket, Key=key)

        CacheService.delete(self._context, key)
