import logging
from hashlib import md5

from starlette import status

from app.config import GRAVATAR_CACHE_EXPIRE
from app.lib.image import DEFAULT_USER_AVATAR, Image
from app.models.types import Email, StorageKey
from app.services.cache_service import CacheContext, CacheService
from app.utils import HTTP

_CTX = CacheContext('Gravatar')


class GravatarQuery:
    @staticmethod
    async def load(email: Email) -> bytes:
        """Load an avatar from Gravatar by email."""
        key = StorageKey(md5(email.lower().encode()).hexdigest())  # noqa: S324

        async def factory() -> bytes:
            logging.debug('Gravatar cache miss')
            r = await HTTP.get(f'https://www.gravatar.com/avatar/{key}?s=512&d=404')
            if r.status_code == status.HTTP_404_NOT_FOUND:
                return DEFAULT_USER_AVATAR
            r.raise_for_status()
            return await Image.normalize_avatar(r.content)

        return await CacheService.get(key, _CTX, factory, ttl=GRAVATAR_CACHE_EXPIRE)
