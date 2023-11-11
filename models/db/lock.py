from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Annotated, Self

import anyio
from pydantic import Field

from models.db.base import Base
from models.str import NonEmptyStr
from utils import utcnow

# request 90
# lock 75
# transaction 60
_DEFAULT_LOCK_TTL = 75

# TODO: expire ttl and test monitoring


class Lock(Base):
    id: Annotated[NonEmptyStr, Field(alias='_id', frozen=True)]

    expires_at: datetime

    @classmethod
    async def acquire(cls, key: str, ttl: float = _DEFAULT_LOCK_TTL) -> Self:
        async with cls._collection().watch([{
            '$match': {
                'operationType': 'delete',
                'documentKey': {'_id': key},
            }
        }]) as stream:
            stream_iter = aiter(stream)

            while True:
                try:
                    lock = cls(id=key, expires_at=utcnow() + timedelta(seconds=ttl))
                    await lock.create()
                    return lock
                except Exception:
                    # TODO: specify exception, logging
                    # wait for lock to expire
                    await anext(stream_iter)


@asynccontextmanager
async def lock(key: str, ttl: float = _DEFAULT_LOCK_TTL):
    lock = await Lock.acquire(key, ttl=ttl)

    try:
        async with anyio.fail_after(ttl - 5):  # 5 seconds margin
            yield lock
    finally:
        await lock.delete()
