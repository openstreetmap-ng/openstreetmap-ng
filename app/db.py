from contextlib import asynccontextmanager

from redis.asyncio import ConnectionPool, Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import POSTGRES_LOG, POSTGRES_URL, REDIS_URL
from app.utils import JSON_DECODE, JSON_ENCODE

_redis_pool = ConnectionPool().from_url(REDIS_URL)


@asynccontextmanager
async def redis():
    async with Redis(connection_pool=_redis_pool) as r:
        yield r


# TODO: pool size (anyio concurrency limit)
_db_engine = create_async_engine(
    POSTGRES_URL,
    # asyncpg doesn't play nicely with JIT
    # https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#disabling-the-postgresql-jit-to-improve-enum-datatype-handling
    connect_args={'server_settings': {'jit': 'off'}},
    echo=POSTGRES_LOG,
    echo_pool=POSTGRES_LOG,
    json_deserializer=JSON_DECODE,
    json_serializer=lambda x: JSON_ENCODE(x).decode(),  # TODO: is decode needed?
    query_cache_size=1024,
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
