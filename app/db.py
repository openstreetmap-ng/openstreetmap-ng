import logging
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import orjson
from psycopg import AsyncConnection, IsolationLevel
from psycopg.types.json import set_json_dumps, set_json_loads
from psycopg_pool import AsyncConnectionPool

from app.config import DUCKDB_MEMORY_LIMIT, DUCKDB_TMPDIR, POSTGRES_URL


async def _configure_connection(conn: AsyncConnection) -> None:
    cursor = conn.cursor

    @wraps(cursor)
    def wrapped(*args, **kwargs):
        # Default to binary mode for all cursors
        # Explicitly set binary=False to revert to text mode
        kwargs.setdefault('binary', True)
        return cursor(*args, **kwargs)

    conn.cursor = wrapped  # pyright: ignore [reportAttributeAccessIssue]


_PSYCOPG_POOL = AsyncConnectionPool(
    POSTGRES_URL,
    min_size=2,
    max_size=100,
    open=False,
    configure=_configure_connection,
    num_workers=3,  # workers for opening new connections
)

set_json_dumps(orjson.dumps)
set_json_loads(orjson.loads)


# TODO: test unicode normalization comparison


@asynccontextmanager
async def psycopg_pool_open():
    """Open and close the psycopg pool."""
    from app.services.migration_service import MigrationService

    await _PSYCOPG_POOL.open()
    await MigrationService.migrate_database()
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
async def db2(write: bool = False, *, autocommit: bool = False, isolation_level: IsolationLevel | None = None):
    """Get a database connection."""
    if autocommit and not write:
        raise ValueError('autocommit=True must be used with write=True')

    async with _PSYCOPG_POOL.connection() as conn:
        if conn.read_only != write:
            await conn.set_read_only(write)
        if conn.autocommit != autocommit:
            await conn.set_autocommit(autocommit)
        if conn.isolation_level != isolation_level:
            await conn.set_isolation_level(isolation_level)

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
