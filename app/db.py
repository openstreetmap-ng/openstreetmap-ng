import logging
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import orjson
from psycopg.types.json import set_json_dumps, set_json_loads
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import DUCKDB_MEMORY_LIMIT, DUCKDB_TMPDIR, POSTGRES_SQLALCHEMY_URL, POSTGRES_URL

_DB_ENGINE = create_async_engine(
    POSTGRES_SQLALCHEMY_URL,
    query_cache_size=1024,
    pool_size=100,  # concurrent connections target
    max_overflow=-1,  # unlimited concurrent connections overflow
    json_deserializer=orjson.loads,
    json_serializer=lambda v: orjson.dumps(v).decode(),
)

_PSYCOPG_POOL = AsyncConnectionPool(
    POSTGRES_URL,
    min_size=2,
    max_size=100,
    open=False,
    num_workers=3,  # workers for opening new connections
)

set_json_dumps(orjson.dumps)
set_json_loads(orjson.loads)


# TODO: test unicode normalization comparison


@asynccontextmanager
async def psycopg_pool_open():
    """Open and close the psycopg pool."""
    await _PSYCOPG_POOL.open()
    try:
        yield _PSYCOPG_POOL
    finally:
        await _PSYCOPG_POOL.close()


def psycopg_pool_open_decorator(func):
    """Convenience decorator to open and close the psycopg pool. For use in scripts."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with psycopg_pool_open():
            return await func(*args, **kwargs)

    return wrapper


@asynccontextmanager
async def db(write: bool = False, *, no_transaction: bool = False):
    """Get a database session."""
    async with AsyncSession(
        _DB_ENGINE,
        expire_on_commit=False,
        close_resets_only=False,  # prevent closed sessions from being reused
    ) as session:
        if no_transaction:
            await session.connection(execution_options={'isolation_level': 'AUTOCOMMIT'})
        yield session
        if write:
            await session.commit()


@asynccontextmanager
async def db2(write: bool = False, *, autocommit: bool = False):
    """Get a database connection."""
    async with _PSYCOPG_POOL.connection() as conn:
        if autocommit and not write:
            raise ValueError('autocommit=True must be used with write=True')
        if conn.read_only != write:
            await conn.set_read_only(write)
        if conn.autocommit != autocommit:
            await conn.set_autocommit(autocommit)
        yield conn
        if not write:
            await conn.rollback()


async def db_update_stats(*, vacuum: bool = False) -> None:
    """Update the database statistics."""
    async with db2(True, autocommit=True) as conn:
        await conn.execute('VACUUM ANALYZE' if vacuum else 'ANALYZE')


@contextmanager
def duckdb_connect(database: str | Path = ':memory:'):
    with (
        TemporaryDirectory(prefix='osm-ng-duckdb-', dir=DUCKDB_TMPDIR) as tmpdir,
        duckdb.connect(
            database,
            config={
                'checkpoint_threshold': '2GB',
                'memory_limit': DUCKDB_MEMORY_LIMIT,
                'preserve_insertion_order': False,
                'temp_directory': tmpdir,
            },
        ) as conn,
    ):
        logging.debug('DuckDB temp_directory: %s', tmpdir)
        conn.sql('PRAGMA enable_progress_bar')
        yield conn
