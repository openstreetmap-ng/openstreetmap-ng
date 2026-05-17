import logging
from asyncio import Future, TaskGroup, sleep
from collections.abc import Callable, Coroutine, Mapping, Sequence
from contextlib import asynccontextmanager, contextmanager, nullcontext
from functools import wraps
from pathlib import Path
from string.templatelib import Template
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any, Literal, LiteralString, ParamSpec, TypeAlias, TypeVar, overload
from weakref import WeakSet

import cython
import duckdb
import orjson
from psycopg import AsyncConnection, IsolationLevel, OperationalError, postgres
from psycopg.abc import AdaptContext
from psycopg.pq import Format
from psycopg.rows import dict_row
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

_P = ParamSpec('_P')
_R = TypeVar('_R')


async def _configure_connection(conn: AsyncConnection):
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


def psycopg_pool_open_decorator(func: Callable[_P, Coroutine[Any, Any, _R]]):
    """Convenience decorator to open and close the psycopg pool. For use in scripts."""

    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs):
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

        async def register_enum(name: str):
            info = await EnumInfo.fetch(conn, name)
            assert info is not None, f'{name!r} enum not found'
            info.register(None)
            adapters.register_loader(info.oid, text_loader)
            logging.debug('Registered database enum %r', name)

        await register_enum('audit_type')
        await register_enum('auth_provider')
        await register_enum('avatar_type')
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
        ):
            info = await TypeInfo.fetch(conn, name)
            assert info is not None, f'{name} type not found'
            register_callable(info, None)
            logging.debug('Registered database type %r', name)

        await register_type('hstore', register_hstore)
        await register_type('geometry', register_shapely)

        async def register_composite_type(name: str):
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


_T = TypeVar('_T')

# Plain values parameter-bind; Template values embed raw SQL expressions
# (e.g., t'statement_timestamp()', t'ST_QuantizeCoordinates({p}, 7)', t'DEFAULT').
_Values: TypeAlias = Mapping[str, object | Template]


@cython.cfunc
def _db_or(conn: AsyncConnection | None, write: cython.bint = False):
    """Pass through provided conn (assumed already configured), else acquire fresh."""
    return nullcontext(conn) if conn is not None else db(write)


@cython.cfunc
def _value_tpl(v) -> Template:
    """Plain value → parameter-bound; Template → raw embed."""
    return v if isinstance(v, Template) else t'{v}'


@cython.cfunc
def _eq_tpl(col: str, v) -> Template:
    """Col = value for WHERE — None becomes IS NULL (parameter-bound NULL never matches via =)."""
    if v is None:
        return t'{col:i} IS NULL'
    if isinstance(v, Template):
        return t'{col:i} = {v:q}'
    return t'{col:i} = {v}'


@cython.cfunc
def _assign_tpl(col: str, v) -> Template:
    """Col = value for SET / VALUES — None binds as SQL NULL (explicit nulling)."""
    if isinstance(v, Template):
        return t'{col:i} = {v:q}'
    return t'{col:i} = {v}'


@cython.cfunc
def _where_tpl(where: Template | Mapping[str, object]) -> Template:
    """Resolve where=Template (passthrough) or where=Mapping (AND-joined equality).

    Mapping mode uses `_eq_tpl`, which translates `None` to `IS NULL`.
    """
    if isinstance(where, Template):
        return where
    if not where:
        raise ValueError('WHERE must be non-empty; refusing to affect all rows')
    return t_and(*(_eq_tpl(c, v) for c, v in where.items()))


@cython.cfunc
def _apply_trailing(
    query: Template,
    limit: int | None,
    offset: int | None,
    for_update: cython.bint,
    conn: AsyncConnection,
) -> Template:
    """Append LIMIT, OFFSET, and FOR UPDATE in standard SQL clause order.

    FOR UPDATE is silently skipped on read-only connections — opportunistic
    locking works in both read-only and write transactions without caller
    branching (helpful for query functions called from either context).

    When LIMIT and FOR UPDATE are combined, Postgres locks only the returned
    rows (LIMIT applies first). Callers wanting "lock all matching" must omit
    LIMIT or use a CTE.
    """
    if limit is not None:
        query = t'{query:q} LIMIT {limit}'
    if offset is not None:
        query = t'{query:q} OFFSET {offset}'
    if for_update and not conn.read_only:
        query = t'{query:q} FOR UPDATE'
    return query


@cython.cfunc
def _no_row_msg(op: str, table: str, hint: str) -> str:
    """Shared assert_returning failure message for db_insert/update/delete."""
    return (
        f'db_{op}(table={table!r}) returned no row; '
        f'pass assert_returning=False if {hint}'
    )


# Hoisted to avoid per-call Composable allocation in helpers below.
_COMMA = SQL(',')
_AND = SQL(' AND ')
_OR = SQL(' OR ')


# ---- Template combinators -------------------------------------------------


def t_and(*conds: Template | None) -> Template:
    """
    AND-combine conditions. None args are skipped. Empty → t'TRUE'.

    Lets callers express conditional WHERE-fragment assembly declaratively:
        return t_and(
            t'user_id = {user_id}' if user_id is not None else None,
            t'NOT closed' if open_only else None,
        )
    """
    filters = [c for c in conds if c is not None]
    if not filters:
        return t'TRUE'
    return _AND.join(filters)


def t_or(*conds: Template | None) -> Template:
    """OR-combine conditions. None args skipped. Empty → t'FALSE'."""
    filters = [c for c in conds if c is not None]
    if not filters:
        return t'FALSE'
    return _OR.join(filters)


def t_order(direction: Literal['asc', 'desc']) -> Template:
    """ASC or DESC keyword Template. Emits verbatim (no parameters)."""
    return t'ASC' if direction == 'asc' else t'DESC'


# ---- Read-side fetch helpers ---------------------------------------------


async def db_fetchone(
    _row_type: type[_T],
    query: Template,
    /,
    *,
    for_update: bool = False,
    conn: AsyncConnection | None = None,
) -> _T | None:
    """
    Fetch a single row as a dict-shaped TypedDict, or None if not found.

    Type arg is positional and exists only for return-type inference; runtime
    uses psycopg's dict_row factory.

    - `for_update=True` appends `FOR UPDATE` to lock the matched row; silently
      skipped if the connection is read-only.
    """
    async with _db_or(conn) as conn:
        query = _apply_trailing(query, None, None, for_update, conn)
        async with await conn.cursor(row_factory=dict_row).execute(query) as r:
            return await r.fetchone()  # type: ignore[return-value]


async def db_fetchall(
    _row_type: type[_T],
    query: Template,
    /,
    *,
    limit: int | None = None,
    offset: int | None = None,
    for_update: bool = False,
    conn: AsyncConnection | None = None,
) -> list[_T]:
    """
    Fetch many rows as dict-shaped TypedDicts.

    - `limit=N` appends `LIMIT N` (parameter-bound) after the query body.
    - `offset=M` appends `OFFSET M` (after LIMIT).
    - `for_update=True` appends `FOR UPDATE`; silently skipped on read-only conn.
      Combined with `limit`, only the returned rows are locked (LIMIT applies first).
    """
    async with _db_or(conn) as conn:
        query = _apply_trailing(query, limit, offset, for_update, conn)
        async with await conn.cursor(row_factory=dict_row).execute(query) as r:
            return await r.fetchall()  # type: ignore[return-value]


async def db_fetchrow(
    query: Template,
    *,
    for_update: bool = False,
    conn: AsyncConnection | None = None,
) -> tuple | None:
    """
    Fetch a single row as a positional tuple. Use for INSERT … RETURNING binding.

    - `for_update=True` appends `FOR UPDATE`; silently skipped on read-only conn.
    """
    async with _db_or(conn) as conn:
        query = _apply_trailing(query, None, None, for_update, conn)
        async with await conn.execute(query) as r:
            return await r.fetchone()


async def db_fetchrows(
    query: Template,
    *,
    limit: int | None = None,
    offset: int | None = None,
    for_update: bool = False,
    conn: AsyncConnection | None = None,
) -> list[tuple]:
    """
    Fetch many rows as positional tuples. Use for multi-column results that don't
    fit a TypedDict shape (e.g. ad-hoc joins, GROUP BY aggregates).

    For `list[tuple[K, V]]` → `dict[K, V]` lookups, wrap with `dict(...)`.

    - `limit=N` appends `LIMIT N`; `offset=M` appends `OFFSET M`;
      `for_update=True` appends `FOR UPDATE` (silently skipped on read-only conn).
      Combined with `limit`, only the returned rows are locked (LIMIT applies first).
    """
    async with _db_or(conn) as conn:
        query = _apply_trailing(query, limit, offset, for_update, conn)
        async with await conn.execute(query) as r:
            return await r.fetchall()


async def db_fetchcol(
    _val_type: Callable[..., _T],
    query: Template,
    /,
    *,
    limit: int | None = None,
    offset: int | None = None,
    for_update: bool = False,
    conn: AsyncConnection | None = None,
) -> list[_T]:
    """
    Fetch a single column as a list of values. Use for find_ids style queries.

    Type arg is positional and exists only for return-type inference; runtime
    uses positional `row[0]` access. Typed as `Callable[..., _T]` to accept
    both classes and `NewType` aliases (which are functions, not types).

    - `limit=N` appends `LIMIT N`; `offset=M` appends `OFFSET M`;
      `for_update=True` appends `FOR UPDATE`. Combined with `limit`, only the
      returned rows are locked (LIMIT applies first).
    """
    async with _db_or(conn) as conn:
        query = _apply_trailing(query, limit, offset, for_update, conn)
        async with await conn.execute(query) as r:
            return [c for (c,) in await r.fetchall()]


async def db_fetchval(
    _val_type: Callable[..., _T],
    query: Template,
    /,
    *,
    for_update: bool = False,
    conn: AsyncConnection | None = None,
) -> _T | None:
    """
    Fetch a single scalar from the first row. COUNT/MAX/EXISTS style.

    Type arg is positional and exists only for return-type inference; runtime
    uses positional `row[0]` access. Typed as `Callable[..., _T]` to accept
    both classes and `NewType` aliases (which are functions, not types).

    - `for_update=True` appends `FOR UPDATE`; silently skipped on read-only conn.
    """
    async with _db_or(conn) as conn:
        query = _apply_trailing(query, None, None, for_update, conn)
        async with await conn.execute(query) as r:
            row = await r.fetchone()
            return row[0] if row is not None else None


async def db_count(
    table: LiteralString,
    *,
    where: Template | Mapping[str, object] | None = None,
    conn: AsyncConnection | None = None,
) -> int:
    """
    `SELECT COUNT(*) FROM table [WHERE …]` returning a non-None int.

    `where=None` (default) counts all rows. `where=Mapping` builds AND-joined
    equality; `where=Template` is used verbatim. COUNT(*) is guaranteed
    non-NULL by PostgreSQL, so no `or 0` is needed at the call site.
    """
    where_sql = t'TRUE' if where is None else _where_tpl(where)
    result = await db_fetchval(
        int, t'SELECT COUNT(*) FROM {table:i} WHERE {where_sql:q}', conn=conn
    )
    assert result is not None, 'COUNT(*) returned NULL (unreachable in PostgreSQL)'
    return result


# ---- Write-side helpers ---------------------------------------------------


@overload
async def db_insert(
    table: LiteralString,
    values: _Values,
    *,
    returning: LiteralString,
    assert_returning: Literal[True] = True,
    on_conflict: Template | None = None,
    conn: AsyncConnection | None = None,
) -> tuple: ...
@overload
async def db_insert(
    table: LiteralString,
    values: _Values,
    *,
    returning: LiteralString,
    assert_returning: Literal[False],
    on_conflict: Template | None = None,
    conn: AsyncConnection | None = None,
) -> tuple | None: ...
@overload
async def db_insert(
    table: LiteralString,
    values: _Values,
    *,
    returning: None = None,
    on_conflict: Template | None = None,
    conn: AsyncConnection | None = None,
) -> int: ...
@overload
async def db_insert(
    table: LiteralString,
    values: _Values,
    *,
    where_not_exists: Template | None,
    returning: LiteralString,
    conn: AsyncConnection | None = None,
) -> tuple | None: ...
@overload
async def db_insert(
    table: LiteralString,
    values: _Values,
    *,
    where_not_exists: Template | None,
    returning: None = None,
    conn: AsyncConnection | None = None,
) -> int: ...
async def db_insert(
    table: LiteralString,
    values: _Values,
    *,
    returning: LiteralString | None = None,
    assert_returning: bool = True,
    on_conflict: Template | None = None,
    where_not_exists: Template | None = None,
    conn: AsyncConnection | None = None,
) -> tuple | None | int:
    """
    INSERT a single row built from a values mapping.

    - Plain dict values are parameter-bound.
    - Template dict values embed as raw SQL expressions
      (e.g. t'statement_timestamp()', t'DEFAULT', t'ST_…').
    - `on_conflict` is a Template appended after ON CONFLICT
      (e.g. t'DO NOTHING' or t'(col) DO UPDATE SET …').
    - `where_not_exists=Template` switches to the `INSERT INTO t (cols) SELECT
      vals WHERE NOT EXISTS (<template>)` form — duplicate-suppression guard
      without a unique constraint. Insert may legitimately not happen; result
      is `tuple | None` (with `returning`) or rowcount (0 or 1). Mutually
      exclusive with `on_conflict`.
    - `returning=<columns>` → returns the RETURNING tuple. Must be a literal
      column list (e.g. `'id'`, `'id, created_at'`). Defaults to asserting
      non-None; pass `assert_returning=False` when the caller expects None
      to be possible (ON CONFLICT DO NOTHING). With `where_not_exists`,
      asserting is bypassed (None is the documented skip signal).
    - `returning=None` → returns rowcount (0 or 1).
    """
    if not values:
        raise ValueError('db_insert requires at least one column')

    cols = _COMMA.join([t'{c:i}' for c in values])
    vals = _COMMA.join([_value_tpl(v) for v in values.values()])
    returning_tpl = t' RETURNING {SQL(returning):q}' if returning is not None else t''

    if where_not_exists is not None:
        if on_conflict is not None:
            raise ValueError(
                'db_insert: where_not_exists is incompatible with on_conflict '
                '(INSERT … SELECT … WHERE NOT EXISTS vs INSERT … VALUES … ON CONFLICT)'
            )
        query = t'INSERT INTO {table:i} ({cols:q}) SELECT {vals:q} WHERE NOT EXISTS ({where_not_exists:q}){returning_tpl:q}'
    else:
        conflict_tpl = (
            t' ON CONFLICT {on_conflict:q}' if on_conflict is not None else t''
        )
        query = t'INSERT INTO {table:i} ({cols:q}) VALUES ({vals:q}){conflict_tpl:q}{returning_tpl:q}'

    async with _db_or(conn, write=True) as conn, await conn.execute(query) as r:
        if returning is not None:
            row = await r.fetchone()
            # With where_not_exists, no-row is the documented skip signal.
            if assert_returning and where_not_exists is None:
                assert row is not None, _no_row_msg(
                    'insert', table, 'this is expected (e.g. ON CONFLICT DO NOTHING)'
                )
            return row
        return r.rowcount


async def db_insert_many(
    table: LiteralString,
    rows: Sequence[_Values],
    *,
    on_conflict: Template | None = None,
    conn: AsyncConnection | None = None,
) -> int:
    """
    Bulk INSERT in a single statement. Returns rowcount.

    All rows must share the same key set (validated against the first row;
    raises ValueError on mismatch). Empty rows is a silent no-op (returns 0).
    RETURNING is intentionally not supported here — sites needing it should
    use a CTE with raw t-string.
    """
    if not rows:
        return 0

    first_keys = tuple(rows[0])
    if not first_keys:
        raise ValueError('db_insert_many rows must have at least one column')
    key_set = set(first_keys)
    for i, row in enumerate(rows[1:], start=1):
        # dict_keys is set-equal-comparable via the Set ABC at runtime — skip the set() alloc.
        if row.keys() != key_set:  # type: ignore[reportUnnecessaryComparison]
            raise ValueError(
                f'db_insert_many row {i} keys {sorted(row)!r} '
                f'differ from row 0 keys {sorted(first_keys)!r}'
            )

    cols = _COMMA.join([t'{c:i}' for c in first_keys])
    rows_sql = _COMMA.join([
        t'({inner:q})'
        for inner in (
            _COMMA.join([_value_tpl(row[c]) for c in first_keys]) for row in rows
        )
    ])
    conflict_tpl = t' ON CONFLICT {on_conflict:q}' if on_conflict is not None else t''
    query = t'INSERT INTO {table:i} ({cols:q}) VALUES {rows_sql:q}{conflict_tpl:q}'

    async with _db_or(conn, write=True) as conn, await conn.execute(query) as r:
        return r.rowcount


@overload
async def db_update(
    table: LiteralString,
    values: _Values,
    *,
    where: Template | Mapping[str, object],
    returning: LiteralString,
    assert_returning: Literal[True] = True,
    conn: AsyncConnection | None = None,
) -> tuple: ...
@overload
async def db_update(
    table: LiteralString,
    values: _Values,
    *,
    where: Template | Mapping[str, object],
    returning: LiteralString,
    assert_returning: Literal[False],
    conn: AsyncConnection | None = None,
) -> tuple | None: ...
@overload
async def db_update(
    table: LiteralString,
    values: _Values,
    *,
    where: Template | Mapping[str, object],
    returning: None = None,
    conn: AsyncConnection | None = None,
) -> int: ...
async def db_update(
    table: LiteralString,
    values: _Values,
    *,
    where: Template | Mapping[str, object],
    returning: LiteralString | None = None,
    assert_returning: bool = True,
    conn: AsyncConnection | None = None,
) -> tuple | None | int:
    """
    UPDATE with a static SET list.

    - `values` keys are columns; values are plain (parameter-bound) or Template
      (raw SQL expression like t'statement_timestamp()' or t'DEFAULT').
    - `where=Mapping` builds AND-joined equality (must be non-empty).
    - `where=Template` is used verbatim.
    - For dynamic SET (conditional clause-by-clause assembly), use raw conn.execute().
    - `returning=<columns>` returns the RETURNING tuple — literal column list
      (asserts non-None by default; pass `assert_returning=False` when WHERE
      may not match).
    """
    if not values:
        raise ValueError('db_update requires at least one column to set')

    set_sql = _COMMA.join([_assign_tpl(c, v) for c, v in values.items()])
    where_sql = _where_tpl(where)
    returning_tpl = t' RETURNING {SQL(returning):q}' if returning is not None else t''
    query = t'UPDATE {table:i} SET {set_sql:q} WHERE {where_sql:q}{returning_tpl:q}'

    async with _db_or(conn, write=True) as conn, await conn.execute(query) as r:
        if returning is not None:
            row = await r.fetchone()
            if assert_returning:
                assert row is not None, _no_row_msg(
                    'update', table, 'WHERE may not match'
                )
            return row
        return r.rowcount


@overload
async def db_delete(
    table: LiteralString,
    *,
    where: Template | Mapping[str, object],
    returning: LiteralString,
    assert_returning: Literal[True] = True,
    conn: AsyncConnection | None = None,
) -> tuple: ...
@overload
async def db_delete(
    table: LiteralString,
    *,
    where: Template | Mapping[str, object],
    returning: LiteralString,
    assert_returning: Literal[False],
    conn: AsyncConnection | None = None,
) -> tuple | None: ...
@overload
async def db_delete(
    table: LiteralString,
    *,
    where: Template | Mapping[str, object],
    returning: None = None,
    conn: AsyncConnection | None = None,
) -> int: ...
async def db_delete(
    table: LiteralString,
    *,
    where: Template | Mapping[str, object],
    returning: LiteralString | None = None,
    assert_returning: bool = True,
    conn: AsyncConnection | None = None,
) -> tuple | None | int:
    """
    DELETE rows matching where.

    - `returning=<columns>` returns the RETURNING tuple — literal column list
      (asserts non-None by default; pass `assert_returning=False` when no row
      may match).
    - `returning=None` returns rowcount.
    """
    where_sql = _where_tpl(where)
    returning_tpl = t' RETURNING {SQL(returning):q}' if returning is not None else t''
    query = t'DELETE FROM {table:i} WHERE {where_sql:q}{returning_tpl:q}'

    async with _db_or(conn, write=True) as conn, await conn.execute(query) as r:
        if returning is not None:
            row = await r.fetchone()
            if assert_returning:
                assert row is not None, _no_row_msg('delete', table, 'no row may match')
            return row
        return r.rowcount
