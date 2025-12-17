import logging
from asyncio import Future, TaskGroup, sleep
from collections.abc import Callable
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from weakref import WeakSet

import cython
import duckdb
import orjson
from psycopg import AsyncConnection, IsolationLevel, OperationalError, postgres
from psycopg.abc import AdaptContext
from psycopg.pq import Format
from psycopg.sql import SQL, Identifier
from psycopg.types import TypeInfo
from psycopg.types.composite import CompositeInfo, register_composite
from psycopg.types.enum import EnumInfo
from psycopg.types.hstore import register_hstore
from psycopg.types.json import set_json_dumps, set_json_loads
from psycopg.types.shapely import register_shapely
from psycopg_pool import AsyncConnectionPool
from sentry_sdk import capture_exception

from app.config import (
    DUCKDB_MEMORY_LIMIT,
    DUCKDB_TMPDIR,
    POSTGRES_STATEMENT_TIMEOUT,
    POSTGRES_URL,
)
from app.middlewares.request_context_middleware import is_request


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

        await register_enum('audit_type')
        await register_enum('auth_provider')
        await register_enum('avatar_type')
        await register_enum('editor')
        await register_enum('mail_source')
        await register_enum('note_event')
        await register_enum('oauth2_code_challenge_method')
        await register_enum('report_action')
        await register_enum('report_category')
        await register_enum('report_type')
        await register_enum('scope')
        await register_enum('trace_visibility')
        await register_enum('user_role')
        await register_enum('user_social_type')
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

        async def register_composite_type(name: str) -> None:
            info = await CompositeInfo.fetch(conn, name)
            assert info is not None, f'{name} type not found'
            register_composite(info, None)
            logging.debug('Registered database composite type %r', name)

        await register_composite_type('user_social')


@asynccontextmanager
async def db(
    write: bool | AsyncConnection | None = False,
    /,
    conn: AsyncConnection | None = None,
    *,
    autocommit: bool = False,
    isolation_level: IsolationLevel | None = None,
    _TIMEOUT_CONNS=WeakSet[AsyncConnection](),
    _TIMEOUT_SQL=SQL('SET statement_timeout = {}').format(
        int(POSTGRES_STATEMENT_TIMEOUT.total_seconds() * 1000)
    ),
):
    """Get a database connection."""
    if not isinstance(write, bool):
        assert conn is None
        conn = write
        write = False

    assert write or not autocommit, 'autocommit=True must be used with write=True'
    read_only = not write

    if conn is not None:
        assert read_only or not conn.read_only, (
            'Provided connection is read-only but write access is requested'
        )
        yield conn
        return

    async with _PSYCOPG_POOL.connection() as conn:
        is_request_: cython.bint = is_request()
        has_timeout: cython.bint = conn in _TIMEOUT_CONNS
        if (is_request_ and not has_timeout) or (not is_request_ and has_timeout):
            if conn.read_only:
                await conn.set_read_only(False)
            if not conn.autocommit:
                await conn.set_autocommit(True)

            if is_request_:
                await conn.execute(_TIMEOUT_SQL)
                _TIMEOUT_CONNS.add(conn)
            else:
                await conn.execute('RESET statement_timeout')
                _TIMEOUT_CONNS.discard(conn)

        if conn.read_only != read_only:
            await conn.set_read_only(read_only)
        if conn.autocommit != autocommit:
            await conn.set_autocommit(autocommit)
        if conn.isolation_level != isolation_level:
            await conn.set_isolation_level(isolation_level)

        yield conn


@asynccontextmanager
async def db_lock(id: int, /):
    """Try to acquire a advisory lock on the database. Periodically send a heartbeat to keep the transaction alive."""
    async with db(True) as conn:

        async def heartbeat():
            while True:
                await sleep(60)
                await conn.execute('SELECT 1')

        async with await conn.execute(
            SQL('SELECT pg_try_advisory_xact_lock(%s::bigint)'),
            (id,),
        ) as r:
            acquired: cython.bint = (await r.fetchone())[0]  # type: ignore

        if acquired:
            async with TaskGroup() as tg:
                heartbeat_task = tg.create_task(heartbeat())
                yield True
                heartbeat_task.cancel()

    if not acquired:
        yield False


async def gather_table_indexes(conn: AsyncConnection, table: str, /) -> dict[str, SQL]:
    """
    Gather non-constraint indexes for a table.

    Returns a dict mapping index names to their CREATE INDEX statements.
    Excludes indexes that are part of constraints (primary keys, unique constraints, etc.).
    """
    async with await conn.execute(
        """
        SELECT pgi.indexname, pgi.indexdef
        FROM pg_indexes pgi
        WHERE pgi.schemaname = 'public'
        AND pgi.tablename = %s
        AND pgi.indexname NOT IN (
            SELECT pgc.conindid::regclass::text
            FROM pg_constraint pgc
            WHERE pgc.conrelid = %s::regclass
        )
        """,
        (table, table),
    ) as r:
        return {name: SQL(sql) for name, sql in await r.fetchall()}


async def gather_table_constraints(
    conn: AsyncConnection, table: str, /
) -> list[tuple[str, SQL]]:
    """
    Gather droppable constraints for a table.

    Returns a list of (constraint_name, constraint_definition) tuples.
    Excludes primary keys, check constraints, and not-null constraints.
    """
    async with await conn.execute(
        """
        SELECT con.conname, pg_get_constraintdef(con.oid)
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        WHERE nsp.nspname = 'public'
        AND rel.relname = %s
        AND con.contype NOT IN ('p', 'c', 'n')
        """,
        (table,),
    ) as r:
        return [(name, SQL(sql)) for name, sql in await r.fetchall()]


@asynccontextmanager
async def without_indexes(conn: AsyncConnection, /, *tables: str, analyze: bool = True):
    """
    Temporarily drop indexes and constraints on tables for faster bulk operations.

    Gathers all non-constraint indexes and droppable constraints (foreign keys, unique constraints)
    for the specified tables, drops them, and recreates them on exit.
    """
    tables_text = (
        f'{tables[0]} table' if len(tables) == 1 else f'{", ".join(tables)} tables'
    )

    # Gather indexes and constraints for all tables
    all_indexes: dict[str, SQL] = {}
    table_constraints: dict[str, list[tuple[str, SQL]]] = {}

    for table in tables:
        indexes = await gather_table_indexes(conn, table)
        all_indexes.update(indexes)
        constraints = await gather_table_constraints(conn, table)
        if constraints:
            table_constraints[table] = constraints

    # Drop constraints first (they may depend on indexes)
    for table, constraints in table_constraints.items():
        await conn.execute(
            SQL('ALTER TABLE {} {}').format(
                Identifier(table),
                SQL(', ').join(
                    SQL('DROP CONSTRAINT {}').format(Identifier(name))
                    for name, _ in constraints
                ),
            )
        )

    # Drop indexes
    if all_indexes:
        await conn.execute(
            SQL('DROP INDEX {}').format(SQL(', ').join(map(Identifier, all_indexes)))
        )

    logging.info(
        'Dropped %d indexes and %d constraints on %s',
        len(all_indexes),
        len(table_constraints),
        tables_text,
    )

    yield

    # Recreate indexes first
    for name, sql in all_indexes.items():
        start = monotonic()
        logging.info('Recreating index %s...', name)
        try:
            await conn.execute(sql)
        except OperationalError as e:
            capture_exception(e)
            logging.critical(
                'Unable to recreate index %s; paused indefinitely', name, exc_info=e
            )
            await Future()
        logging.info('Recreated index %s in %.1fs', name, monotonic() - start)

    # Then recreate constraints
    for table, constraints in table_constraints.items():
        start = monotonic()
        logging.info('Recreating constraints on %s...', table)
        await conn.execute(
            SQL('ALTER TABLE {} {}').format(
                Identifier(table),
                SQL(', ').join(
                    SQL('ADD CONSTRAINT {} {}').format(Identifier(name), sql)
                    for name, sql in constraints
                ),
            )
        )
        logging.info('Recreated constraints on %s in %.1fs', table, monotonic() - start)

    # Update statistics for query planner
    if analyze:
        start = monotonic()
        logging.info('Analyzing %s...', tables_text)
        await conn.execute(
            SQL('ANALYZE {}').format(SQL(', ').join(map(Identifier, tables)))
        )
        logging.info('Analyzed %s in %.1fs', tables_text, monotonic() - start)

    logging.info('Recreated indexes and constraints on %s', tables_text)


@contextmanager
def duckdb_connect(database: str | Path = ':memory:', *, progress: bool = True):
    with (
        TemporaryDirectory(prefix='osm-ng-duckdb-', dir=DUCKDB_TMPDIR) as tmpdir,
        duckdb.connect(
            database,
            config={
                'checkpoint_threshold': '2GB',
                'memory_limit': DUCKDB_MEMORY_LIMIT,
                'preserve_insertion_order': 'false',
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
