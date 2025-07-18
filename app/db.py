import logging
from collections.abc import Callable
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from pathlib import Path
from tempfile import TemporaryDirectory

import cython
import duckdb
import orjson
from psycopg import AsyncConnection, IsolationLevel, postgres
from psycopg.abc import AdaptContext
from psycopg.pq import Format
from psycopg.types import TypeInfo
from psycopg.types.enum import EnumInfo
from psycopg.types.hstore import register_hstore
from psycopg.types.json import set_json_dumps, set_json_loads
from psycopg.types.shapely import register_shapely
from psycopg_pool import AsyncConnectionPool

from app.config import (
    DUCKDB_MEMORY_LIMIT,
    DUCKDB_TMPDIR,
    POSTGRES_URL,
)


async def _configure_connection(conn: AsyncConnection) -> None:
    cursor = conn.cursor

    @wraps(cursor)
    def wrapped(*args, **kwargs):
        # Default to binary mode for all cursors
        # Explicitly set binary=False to revert to text mode
        kwargs.setdefault('binary', True)
        return cursor(*args, **kwargs)

    conn.cursor = wrapped  # type: ignore


@cython.cfunc
def _init_pool():
    global _PSYCOPG_POOL
    _PSYCOPG_POOL = AsyncConnectionPool(  # pyright: ignore [reportConstantRedefinition]
        POSTGRES_URL,
        min_size=2,
        max_size=100,
        open=False,
        configure=_configure_connection,
        num_workers=3,  # workers for opening new connections
    )


_PSYCOPG_POOL: AsyncConnectionPool

set_json_dumps(orjson.dumps)
set_json_loads(orjson.loads)


# TODO: test unicode normalization comparison


@asynccontextmanager
async def psycopg_pool_open():
    """Open and close the psycopg pool."""
    from app.services.migration_service import MigrationService  # noqa: PLC0415

    _init_pool()
    async with _PSYCOPG_POOL:
        await MigrationService.migrate_database()
        await _register_types()
        # Reset the connection pool to ensure the new types are used.

    _init_pool()
    async with _PSYCOPG_POOL:
        yield


def psycopg_pool_open_decorator(func):
    """Convenience decorator to open and close the psycopg pool. For use in scripts."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with psycopg_pool_open():
            return await func(*args, **kwargs)

    return wrapper


async def _register_types():
    """
    Register db support for additional types.
    https://www.psycopg.org/psycopg3/docs/basic/pgtypes.html
    """
    async with db() as conn:
        adapters = postgres.adapters
        text_loader = adapters.get_loader(adapters.types['text'].oid, Format.BINARY)
        assert text_loader is not None, 'Binary text loader not found'

        async def register_enum(name: str) -> None:
            info = await EnumInfo.fetch(conn, name)
            assert info is not None, f'{name} enum not found'
            info.register(None)
            adapters.register_loader(info.oid, text_loader)
            logging.debug('Registered database enum %r', name)

        await register_enum('auth_provider')
        await register_enum('avatar_type')
        await register_enum('editor')
        await register_enum('mail_source')
        await register_enum('note_event')
        await register_enum('oauth2_code_challenge_method')
        await register_enum('scope')
        await register_enum('trace_visibility')
        await register_enum('user_role')
        await register_enum('user_subscription_target')
        await register_enum('user_token_type')

        async def register_type(
            name: str,
            register_callable: Callable[[TypeInfo, AdaptContext | None], None],
        ) -> None:
            info = await TypeInfo.fetch(conn, name)
            assert info is not None, f'{name} type not found'
            register_callable(info, None)
            logging.debug('Registered database type %r', name)

        await register_type('hstore', register_hstore)
        await register_type('geometry', register_shapely)


@asynccontextmanager
async def db(
    write: bool = False,
    *,
    autocommit: bool = False,
    isolation_level: IsolationLevel | None = None,
):
    """Get a database connection."""
    assert write or not autocommit, 'autocommit=True must be used with write=True'

    read_only = not write

    async with _PSYCOPG_POOL.connection() as conn:
        if conn.read_only != read_only:
            await conn.set_read_only(read_only)
        if conn.autocommit != autocommit:
            await conn.set_autocommit(autocommit)
        if conn.isolation_level != isolation_level:
            await conn.set_isolation_level(isolation_level)

        yield conn


@contextmanager
def duckdb_connect(database: str | Path = ':memory:', *, progress: bool = True):
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

        if progress:
            conn.sql('PRAGMA enable_progress_bar')

        # Disable replacement scans because they are bug-prone.
        # Use duckdb.register to register data explicitly.
        conn.sql('SET python_enable_replacements = FALSE')

        yield conn
