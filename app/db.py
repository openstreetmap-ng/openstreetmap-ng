from collections.abc import Generator
from contextlib import asynccontextmanager
from typing import Any

from redis.asyncio import ConnectionPool, Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import POSTGRES_LOG, POSTGRES_URL, REDIS_URL
from app.utils import MSGSPEC_JSON_DECODER, MSGSPEC_JSON_ENCODER

_redis_pool = ConnectionPool().from_url(REDIS_URL)


@asynccontextmanager
async def redis():
    async with Redis(connection_pool=_redis_pool) as r:
        yield r


_db_engine = create_async_engine(
    POSTGRES_URL,
    echo=POSTGRES_LOG,
    echo_pool=POSTGRES_LOG,
    json_deserializer=MSGSPEC_JSON_DECODER.decode,
    json_serializer=lambda x: MSGSPEC_JSON_ENCODER.encode(x).decode(),
    query_cache_size=512,
)


@asynccontextmanager
async def db() -> Generator[AsyncSession, Any, None]:
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
async def db_autocommit() -> Generator[AsyncSession, Any, None]:
    """
    Get a database session that commits automatically on exit.
    """

    async with db() as session:
        yield session
        await session.commit()


# TODO: test unicode normalization comparison
