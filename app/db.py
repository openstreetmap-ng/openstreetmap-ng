from contextlib import asynccontextmanager

from redis.asyncio import ConnectionPool, Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import POSTGRES_URL, REDIS_URL

_redis_pool = ConnectionPool().from_url(REDIS_URL)


@asynccontextmanager
async def redis():
    async with Redis(connection_pool=_redis_pool) as r:
        yield r


_db_engine = create_async_engine(
    POSTGRES_URL,
    echo=True,  # TODO: echo testing only
    echo_pool=True,
)


@asynccontextmanager
async def db():
    # close_resets_only=False: prevent closed sessions from being reused
    async with AsyncSession(_db_engine, expire_on_commit=False, close_resets_only=False) as session:
        yield session


# TODO: test unicode normalization comparison
