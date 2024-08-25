from hashlib import md5
from typing import override

from starlette import status

from app.lib.file_cache import FileCache
from app.lib.image import Image
from app.lib.storage.base import StorageBase
from app.limits import GRAVATAR_CACHE_EXPIRE
from app.utils import http_get


class GravatarStorage(StorageBase):
    """
    File storage based on Gravatar (read-only).

    Uses FileCache for response caching.
    """

    __slots__ = ('_fc',)

    def __init__(self, context: str = 'gravatar'):
        super().__init__(context)
        self._fc = FileCache(context)

    @override
    async def load(self, key: str) -> bytes:
        """
        Load an avatar from Gravatar by email.
        """
        key_hashed = md5(key.lower().encode()).hexdigest()  # noqa: S324
        data = await self._fc.get(key)
        if data is not None:
            return data

        async with http_get(f'https://www.gravatar.com/avatar/{key_hashed}?s=512&d=404') as r:
            if r.status == status.HTTP_404_NOT_FOUND:
                data = Image.default_avatar
            else:
                r.raise_for_status()
                data = await r.read()
                data = await Image.normalize_avatar(data)

        await self._fc.set(key_hashed, data, ttl=GRAVATAR_CACHE_EXPIRE)
        return data
