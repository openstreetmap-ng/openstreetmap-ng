from contextlib import asynccontextmanager

from redis.asyncio import ConnectionPool, Redis
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import POSTGRES_URL, TEST_ENV, VALKEY_URL
from app.utils import JSON_DECODE, JSON_ENCODE

if TEST_ENV:

    @asynccontextmanager
    async def valkey():
        async with Redis.from_url(VALKEY_URL) as r:
            yield r
else:
    _valkey_pool = ConnectionPool().from_url(VALKEY_URL)

    @asynccontextmanager
    async def valkey():
        async with Redis(connection_pool=_valkey_pool) as r:
            yield r


_db_engine = create_async_engine(
    POSTGRES_URL,
    # asyncpg enum doesn't play nicely with JIT
    # https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#disabling-the-postgresql-jit-to-improve-enum-datatype-handling
    connect_args={'server_settings': {'jit': 'off'}},
    json_deserializer=JSON_DECODE,
    json_serializer=lambda x: JSON_ENCODE(x).decode(),
    query_cache_size=1024,
    **(
        {
            'poolclass': NullPool,
        }
        if TEST_ENV
        else {
            'pool_size': 10,
            'max_overflow': -1,
        }
    ),
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


# TODO: test unicode normalization comparison
