import logging
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import orjson
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from valkey.asyncio import ConnectionPool, Valkey

from app.config import DUCKDB_MEMORY_LIMIT, DUCKDB_TMPDIR, POSTGRES_SQLALCHEMY_URL, VALKEY_URL

_DB_ENGINE = create_async_engine(
    POSTGRES_SQLALCHEMY_URL,
    query_cache_size=1024,
    pool_size=100,  # concurrent connections target
    max_overflow=-1,  # unlimited concurrent connections overflow
    json_deserializer=orjson.loads,
    json_serializer=lambda v: orjson.dumps(v).decode(),
)


_VALKEY_POOL = ConnectionPool.from_url(VALKEY_URL)

# TODO: test unicode normalization comparison


@asynccontextmanager
async def db(write: bool = False):
    """Get a database session."""
    async with AsyncSession(
        _DB_ENGINE,
        expire_on_commit=False,
        close_resets_only=False,  # prevent closed sessions from being reused
    ) as session:
        yield session
        if write:
            await session.commit()


async def db_update_stats(*, vacuum: bool = False) -> None:
    """Update the database statistics."""
    async with db() as session:
        await session.connection(execution_options={'isolation_level': 'AUTOCOMMIT'})
        await session.execute(text('VACUUM ANALYZE') if vacuum else text('ANALYZE'))


@asynccontextmanager
async def valkey():
    async with Valkey(connection_pool=_VALKEY_POOL) as r:
        yield r


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
