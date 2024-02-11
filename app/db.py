from contextlib import asynccontextmanager

import orjson
from redis.asyncio import ConnectionPool, Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import POSTGRES_LOG, POSTGRES_URL, REDIS_URL

_redis_pool = ConnectionPool().from_url(REDIS_URL)


@asynccontextmanager
async def redis():
    async with Redis(connection_pool=_redis_pool) as r:
        yield r


# TODO: pool size (anyio concurrency limit)
_db_engine = create_async_engine(
    POSTGRES_URL,
    echo=POSTGRES_LOG,
    echo_pool=POSTGRES_LOG,
    json_deserializer=orjson.loads,
    json_serializer=lambda x: orjson.dumps(x).decode(),
    query_cache_size=512,
)


@asynccontextmanager
async def db():
    """
    Get a database session.
    """

    async with AsyncSession(
        _db_engine,
        expire_on_commit=False,
        close_resets_only=False,  # prevent closed sessions from being reused
    ) as session:
        yield session


@asynccontextmanager
async def db_autocommit():
    """
    Get a database session that commits automatically on exit.
    """

    async with db() as session:
        yield session
        await session.commit()


# TODO: test unicode normalization comparison
