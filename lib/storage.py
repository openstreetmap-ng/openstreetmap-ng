import secrets
from abc import ABC
from hashlib import md5

import aioboto3
from anyio import Path
from fastapi import status

from config import FILE_DATA_DIR
from lib.crypto import hash_urlsafe
from lib.file_cache import FileCache
from utils import HTTP

_S3 = aioboto3.Session()


def _get_key(data: bytes, suffix: str, random: bool) -> str:
    if random:
        return secrets.token_urlsafe(32) + suffix
    else:
        return hash_urlsafe(data) + suffix


class Storage(ABC):
    _context: str

    def __init__(self, context: str):
        self._context = context

    @staticmethod
    async def load(key: str) -> bytes:
        raise NotImplementedError()

    @staticmethod
    async def save(data: bytes, suffix: str, *, random: bool = True) -> str:
        raise NotImplementedError()

    @staticmethod
    async def delete(key: str) -> None:
        raise NotImplementedError()


class LocalStorage(Storage):
    async def _get_path(self, key: str) -> Path:
        d1 = key[:1]
        d2 = key[1:3]
        dir = FILE_DATA_DIR / self._context / d1 / d2
        await dir.mkdir(parents=True, exist_ok=True)
        return dir / key

    async def load(self, key: str) -> bytes:
        path = await self._get_path(key)
        return await path.read_bytes()

    async def save(self, data: bytes, suffix: str, *, random: bool = True) -> str:
        key = _get_key(data, suffix, random)
        path = await self._get_path(key)
        async with await path.open('xb') as f:
            await f.write(data)
        return key

    async def delete(self, key: str) -> None:
        path = await self._get_path(key)
        await path.unlink(missing_ok=True)


class S3Storage(Storage):
    def __init__(self, context: str):
        super().__init__(context)
        self._cache = FileCache(context)

    async def load(self, key: str) -> bytes:
        if not (data := await self._cache.get(key)):
            async with _S3.client('s3') as s3:
                data = await (await s3.get_object(Bucket=self._context, Key=key))['Body'].read()
            await self._cache.set(key, data)
        return data

    async def save(self, data: bytes, suffix: str, *, random: bool = True) -> str:
        key = _get_key(data, suffix, random)
        async with _S3.client('s3') as s3:
            await s3.put_object(Bucket=self._context, Key=key, Body=data)
        return key

    async def delete(self, key: str) -> None:
        async with _S3.client('s3') as s3:
            await s3.delete_object(Bucket=self._context, Key=key)
        await self._cache.pop(key)


class GravatarStorage(Storage):
    def __init__(self, context: str = 'gravatar'):
        super().__init__(context)
        self._cache = FileCache(context)

    async def load(self, key: str) -> bytes:
        key = md5(key.lower()).hexdigest()
        if not (data := await self._cache.get(key)):
            r = await HTTP.get(f'https://www.gravatar.com/avatar/{key}?s=512&d=404')
            if r.status_code == status.HTTP_404_NOT_FOUND:
                # TODO: return default image
                raise NotImplementedError()
            r.raise_for_status()
            data = r.content
            await self._cache.set(key, data)
        return data

    async def save(self, data: bytes, suffix: str, *, random: bool = True) -> str:
        raise NotImplementedError('%r is read-only', GravatarStorage.__qualname__)

    async def delete(self, key: str) -> None:
        raise NotImplementedError('%r is read-only', GravatarStorage.__qualname__)
