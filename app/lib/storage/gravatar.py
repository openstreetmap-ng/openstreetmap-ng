from datetime import timedelta
from hashlib import md5

from fastapi import status

from app.lib.avatar import Avatar
from app.lib.file_cache import FileCache
from app.lib.storage.base import StorageBase
from app.utils import HTTP

_local_cache_ttl = timedelta(days=1)


class GravatarStorage(StorageBase):
    """
    File storage based on Gravatar (read-only).

    Uses FileCache for local caching.
    """

    def __init__(self, context: str = 'gravatar'):
        super().__init__(context)
        self._fc = FileCache(context)

    async def load(self, email: str) -> bytes:
        key = md5(email.lower()).hexdigest()  # noqa: S324

        if (data := await self._fc.get(key)) is not None:
            return data

        r = await HTTP.get(f'https://www.gravatar.com/avatar/{key}?s=512&d=404')

        if r.status_code == status.HTTP_404_NOT_FOUND:
            data = await Avatar.get_default_image()
        else:
            r.raise_for_status()
            data = r.content
            data = Avatar.normalize_image(data)

        await self._fc.set(key, data, ttl=_local_cache_ttl)
        return data
