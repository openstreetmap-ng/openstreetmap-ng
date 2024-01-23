from collections.abc import Awaitable, Callable

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import load_only

from app.db import DB
from app.lib.crypto import hash_bytes
from app.lib.date_utils import utcnow
from app.limits import CACHE_DEFAULT_EXPIRE
from app.models.db.cache_entry import CacheEntry

# NOTE: ideally we would use Redis for caching, but for now this will be good enough


def _hash_key(key: str, context: str) -> bytes:
    return hash_bytes(key, context=context)


class CacheService:
    @staticmethod
    async def get_one_by_id(cache_id: bytes, factory: Callable[[], Awaitable[str]]) -> str:
        """
        Get a value from the cache by id.

        If the value is not in the cache, call the async factory to generate it.
        """

        async with DB() as session:
            entry = await session.get(CacheEntry, cache_id, options=[load_only(CacheEntry.value, raiseload=True)])

            if not entry:
                value = await factory()
                entry = CacheEntry(
                    id=cache_id,
                    value=value,
                    expires_at=utcnow() + CACHE_DEFAULT_EXPIRE,
                )

                stmt = insert(CacheEntry).values(entry).on_conflict_do_nothing(index_elements=[CacheEntry.id])

                await session.execute(stmt)

            return entry.value

    @staticmethod
    async def get_one_by_key(key: str, context: str, factory: Callable[[], Awaitable[str]]) -> str:
        """
        Get a value from the cache by key string.

        Context is used to namespace the cache and prevent collisions.

        If the value is not in the cache, call the async factory to generate it.
        """

        cache_id = _hash_key(key, context)
        return await CacheService.get_one_by_id(cache_id, factory)
