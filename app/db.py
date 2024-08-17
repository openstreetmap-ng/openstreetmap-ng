from contextlib import asynccontextmanager
from typing import Any

from redis.asyncio import ConnectionPool, Redis
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import POSTGRES_URL, TEST_ENV, VALKEY_URL
from app.utils import JSON_DECODE, json_encodes

_db_engine_kwargs: dict[str, Any] = (
    {
        'poolclass': NullPool,  # disable connection pooling
    }
    if TEST_ENV
    else {
        'pool_size': 10,  # concurrent connections target
        'max_overflow': -1,  # unlimited concurrent connections overflow
    }
)

_db_engine = create_async_engine(
    POSTGRES_URL,
    # asyncpg enum doesn't play nicely with JIT
    # https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#disabling-the-postgresql-jit-to-improve-enum-datatype-handling
    connect_args={'server_settings': {'jit': 'off'}},
    json_deserializer=JSON_DECODE,
    json_serializer=json_encodes,
    query_cache_size=1024,
    **_db_engine_kwargs,
)

_valkey_pool = ConnectionPool.from_url(VALKEY_URL)

# TODO: test unicode normalization comparison


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
async def db_commit():
    """
    Get a database session that commits on exit.
    """
    async with db() as session:
        yield session
        await session.commit()


async def db_update_stats(*, vacuum: bool = False) -> None:
    """
    Update the database statistics.
    """
    async with db() as session:
        await session.connection(execution_options={'isolation_level': 'AUTOCOMMIT'})
        await session.execute(text('VACUUM ANALYZE') if vacuum else text('ANALYZE'))


@asynccontextmanager
async def valkey():
    if TEST_ENV:
        async with Redis.from_url(VALKEY_URL) as r:
            yield r
    else:
        async with Redis(connection_pool=_valkey_pool) as r:
            yield r
