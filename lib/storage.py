import secrets
from abc import ABC
from hashlib import md5

import aioboto3
from fastapi import status

from config import FILE_DATA_DIR
from lib.crypto import hash_urlsafe
from lib.file_cache import FileCache
from utils import HTTP

_S3 = aioboto3.Session()


def _get_key(data: bytes, suffix: str, random: bool) -> str:
    """
    Generate a key for a file.

    If random is `False`, the generated key is deterministic.
    """

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
        """
        Load a file from storage by key string.
        """

        raise NotImplementedError

    @staticmethod
    async def save(data: bytes, suffix: str, *, random: bool = True) -> str:
        """
        Save a file to storage by key string.
        """

        raise NotImplementedError

    @staticmethod
    async def delete(key: str) -> None:
        """
        Delete a key from storage.
        """

        raise NotImplementedError


class LocalStorage(Storage):
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
        key = _get_key(data, suffix, random)
        await self._fc.set(key, data)

    async def delete(self, key: str) -> None:
        await self._fc.delete(key)


class S3Storage(Storage):
    """
    File storage based on AWS S3.

    Uses FileCache for local caching.
    """

    def __init__(self, context: str):
        super().__init__(context)
        self._fc = FileCache(context)

    async def load(self, key: str) -> bytes:
        if data := await self._fc.get(key):
            return data

        async with _S3.client('s3') as s3:
            data = await (await s3.get_object(Bucket=self._context, Key=key))['Body'].read()

        await self._fc.set(key, data)
        return data

    async def save(self, data: bytes, suffix: str, *, random: bool = True) -> str:
        key = _get_key(data, suffix, random)

        async with _S3.client('s3') as s3:
            await s3.put_object(Bucket=self._context, Key=key, Body=data)

        return key

    async def delete(self, key: str) -> None:
        async with _S3.client('s3') as s3:
            await s3.delete_object(Bucket=self._context, Key=key)

        await self._fc.delete(key)


class GravatarStorage(Storage):
    """
    File storage based on Gravatar (read-only).

    Uses FileCache for local caching.
    """

    def __init__(self, context: str = 'gravatar'):
        super().__init__(context)
        self._fc = FileCache(context)

    async def load(self, email: str) -> bytes:
        key = md5(email.lower()).hexdigest()  # noqa: S324

        if data := await self._fc.get(key):
            return data

        r = await HTTP.get(f'https://www.gravatar.com/avatar/{key}?s=512&d=404')

        if r.status_code == status.HTTP_404_NOT_FOUND:
            # TODO: return default image
            raise NotImplementedError

        r.raise_for_status()
        data = r.content

        await self._fc.set(key, data)
        return data
