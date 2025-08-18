import asyncio
import logging
import re
from argparse import ArgumentParser
from asyncio import Condition, Lock, TaskGroup, create_subprocess_shell
from asyncio.subprocess import PIPE, Process
from contextlib import nullcontext
from io import TextIOWrapper
from itertools import starmap
from pathlib import Path
from shlex import quote
from time import monotonic
from typing import Literal, NamedTuple, get_args

from psycopg.abc import Query
from psycopg.sql import SQL, Identifier
from zstandard import ZstdDecompressor

from app.config import POSTGRES_URL, PRELOAD_DIR
from app.db import db, psycopg_pool_open_decorator
from app.models.element import (
    TYPED_ELEMENT_ID_NODE_MAX,
    TYPED_ELEMENT_ID_RELATION_MAX,
    TYPED_ELEMENT_ID_WAY_MIN,
)
from app.queries.element_query import ElementQuery
from app.services.migration_service import MigrationService
from app.utils import calc_num_workers

_Mode = Literal['preload', 'replication']

# Sorted from heaviest to lightest tables
_Table = Literal[
    'element',
    'changeset',
    'changeset_bounds',
    'note_comment',
    'note',
    'user',
]


class WeightedSemaphore:
    def __init__(self, value: int, /):
        assert value > 0
        self._value = value
        self._cond = Condition()

    async def acquire(self, weight: int, /) -> None:
        assert weight > 0
        async with self._cond:
            while self._value < weight:
                await self._cond.wait()
            self._value -= weight

    async def release(self, weight: int, /) -> None:
        assert weight > 0
        async with self._cond:
            self._value += weight
            self._cond.notify_all()


class _PostgresSettings(NamedTuple):
    max_parallel_workers: int
    max_parallel_maintenance_workers: int
    maintenance_work_mem: str


class _TimescaleChunk(NamedTuple):
    id: int
    hypertable_id: int
    schema_name: str
    table_name: str


_TABLE_LOCK = Lock()
_NUM_WORKERS_COPY = calc_num_workers(max=8)

# Optimize loading by creating some indexes on subsets of the chunks
_INDEX_CHUNKS_RANGE: dict[str, tuple[int, int]] = {
    'element_point_idx': (0, TYPED_ELEMENT_ID_NODE_MAX),
    'element_members_idx': (TYPED_ELEMENT_ID_WAY_MIN, TYPED_ELEMENT_ID_RELATION_MAX),
    'element_members_history_idx': (
        TYPED_ELEMENT_ID_WAY_MIN,
        TYPED_ELEMENT_ID_RELATION_MAX,
    ),
}


def _get_csv_path(table: _Table) -> Path:
    return PRELOAD_DIR.joinpath(f'{table}.csv.zst')


def _get_csv_header(path: Path) -> str:
    with (
        path.open('rb') as f,
        ZstdDecompressor().stream_reader(f) as stream,
        TextIOWrapper(stream) as reader,
    ):
        return reader.readline().strip()


async def _detect_settings() -> _PostgresSettings:
    async with (
        db() as conn,
        await conn.execute(
            """
            SELECT
                current_setting('max_parallel_workers')::integer,
                current_setting('max_parallel_maintenance_workers')::integer,
                current_setting('maintenance_work_mem')
            """,
        ) as r,
    ):
        return _PostgresSettings(*(await r.fetchone()))  # type: ignore


async def _gather_table_indexes(table: _Table) -> dict[str, SQL]:
    async with (
        db() as conn,
        await conn.execute(
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
        ) as r,
    ):
        return {name: SQL(sql) for name, sql in await r.fetchall()}


async def _gather_table_constraints(table: _Table) -> list[tuple[str, SQL]]:
    async with (
        db() as conn,
        await conn.execute(
            SQL("""
            SELECT con.conname, pg_get_constraintdef(con.oid)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = 'public'
            AND rel.relname = %s
            AND con.contype NOT IN ('c', 'n') {}
            """).format(
                SQL(
                    """
                    AND con.contype != 'p'  -- Exclude primary key constraints
                    AND con.conname NOT LIKE '%%_id_not_null'
                    """
                    if table == 'user'
                    else ''
                )
            ),
            (table,),
        ) as r,
    ):
        return [(name, SQL(sql)) for name, sql in await r.fetchall()]


async def _gather_table_chunks(table: _Table) -> list[_TimescaleChunk]:
    async with (
        db() as conn,
        await conn.execute(
            """
            SELECT ck.id, ck.hypertable_id, ck.schema_name, ck.table_name
            FROM _timescaledb_catalog.hypertable ht
            JOIN _timescaledb_catalog.chunk ck ON ht.id = ck.hypertable_id
            WHERE ht.schema_name = 'public'
            AND ht.table_name = %s
            """,
            (table,),
        ) as r,
    ):
        return list(starmap(_TimescaleChunk, await r.fetchall()))


async def _filter_index_chunks(
    name: str, chunks: list[_TimescaleChunk]
) -> list[_TimescaleChunk]:
    chunks_range = _INDEX_CHUNKS_RANGE.get(name)
    if chunks_range is None:
        return chunks

    async with (
        db() as conn,
        await conn.execute(
            """
            SELECT chunk_name
            FROM timescaledb_information.chunks
            WHERE chunk_name = ANY(%s)
            AND range_end_integer > %s
            AND range_start_integer <= %s
            """,
            ([c.table_name for c in chunks], *chunks_range),
        ) as r,
    ):
        chunk_names = {c for (c,) in await r.fetchall()}
        return [c for c in chunks if c.table_name in chunk_names]


async def _load_table(mode: _Mode, table: _Table) -> None:
    if mode == 'preload' or table in {'note', 'note_comment'}:
        path = _get_csv_path(table)

        # Replication supports optional data files
        if mode == 'replication' and not path.is_file():
            logging.info('Skipped loading %s table (source file not found)', table)
            return

        copy_paths = [path]
        header = _get_csv_header(path)
        program = f'zstd -d --stdout {" ".join(f"{quote(str(p.absolute()))}" for p in copy_paths)}'
    else:
        program = f'replication-convert {table}'
        proc = await create_subprocess_shell(f'{program} --header-only', stdout=PIPE)
        header = (await proc.communicate())[0].decode().strip()

    # Load the data
    columns = [f'"{c}"' for c in header.split(',')]
    proc: Process | None = None

    try:
        logging.info('Populating %s table (%d columns)...', table, len(columns))
        proc = await create_subprocess_shell(
            f'{program} | timescaledb-parallel-copy'
            ' --batch-size=50000'
            f' --columns={quote(",".join(columns))}'
            f' --connection={quote(POSTGRES_URL)}'
            f' --skip-header=true'
            ' --reporting-period=30s'
            f' --table={quote(table)}'
            f' --workers={_NUM_WORKERS_COPY}',
        )
        exit_code = await proc.wait()
        if exit_code:
            raise RuntimeError(f'Subprocess failed with exit code {exit_code}')

    except KeyboardInterrupt:
        if proc is not None:
            proc.terminate()
        raise


async def _load_tables(mode: _Mode) -> None:
    all_tables: tuple[_Table, ...] = get_args(_Table)

    settings = await _detect_settings()
    maintenance_parallelism = (
        int(settings.max_parallel_workers / settings.max_parallel_maintenance_workers)
        or 1
    )
    maintenance_semaphore = WeightedSemaphore(maintenance_parallelism * 2)
    logging.info('Detected maintenance parallelism: %d', maintenance_parallelism)

    logging.info('Truncating tables: %r', all_tables)
    async with db(True, autocommit=True) as conn:
        await conn.execute(
            SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(
                SQL(',').join(map(Identifier, all_tables))
            )
        )

    logging.info('Gathering indexes and constraints')
    table_data: dict[_Table, tuple[dict[str, SQL], list[tuple[str, SQL]]]] = {}
    for table in all_tables:
        indexes = await _gather_table_indexes(table)
        assert indexes, f'No indexes found for {table} table'
        constraints = await _gather_table_constraints(table)
        table_data[table] = (indexes, constraints)

    async with db(True, autocommit=True) as conn:
        for table in all_tables:
            indexes, constraints = table_data[table]

            logging.info(
                'Dropping %d indexes from %s: %r',
                len(indexes),
                table,
                indexes,
            )
            await conn.execute(
                """
                UPDATE pg_index SET indislive = FALSE
                WHERE indexrelid = ANY(%s::regclass[])
                """,
                (list(indexes),),
            )

            if constraints:
                logging.info(
                    'Dropping %d constraints from %s: %r',
                    len(constraints),
                    table,
                    constraints,
                )
                await conn.execute(
                    SQL('ALTER TABLE {} {}').format(
                        Identifier(table),
                        SQL(',').join(
                            SQL('DROP CONSTRAINT {}').format(Identifier(name))
                            for name, _ in constraints
                        ),
                    )
                )

    async def load_task(table: _Table) -> None:
        async with _TABLE_LOCK if mode == 'replication' else nullcontext():
            await _load_table(mode, table)

    async def execute(sql: Query) -> None:
        # Increase parallelization for GIN/GiST indexes
        # TODO: remove in postgres 18+ (native parallelization)
        permits = 1 if re.search(r' USING (gin|gist) ', str(sql)) else 2

        await maintenance_semaphore.acquire(permits)
        try:
            async with db(True, autocommit=True) as conn:
                ts = monotonic()
                await conn.execute(sql)
                logging.debug('Executed %r in %.1fs', sql, monotonic() - ts)
        finally:
            await maintenance_semaphore.release(permits)

    async def index_task(table: _Table, tg: TaskGroup) -> None:
        chunks = await _gather_table_chunks(table)
        indexes, constraints = table_data[table]
        logging.info(
            'Recreating indexes and constraints on %s table (%d chunks)...',
            table,
            len(chunks),
        )

        async with db(True, autocommit=True) as conn:
            await conn.execute(
                """
                UPDATE pg_index SET indislive = TRUE
                WHERE indexrelid = ANY(%s::regclass[])
                """,
                (list(indexes),),
            )

            if not chunks:
                for name in indexes:
                    await conn.execute(SQL('DROP INDEX {}').format(Identifier(name)))

            # Create indexes in reverse order, as heavy indexes tend to be last
            for name, sql in reversed(indexes.items()):
                # Handle normal tables
                if not chunks:
                    tg.create_task(execute(sql))
                    continue

                # Handle hypertables
                for chunk in await _filter_index_chunks(name, chunks):
                    chunk_name = f'{chunk.table_name}_{name}'
                    chunk_sql = SQL(
                        sql.as_string()
                        .replace(name, chunk_name)
                        .replace(
                            f'public.{table}', f'{chunk.schema_name}.{chunk.table_name}'
                        )  # type: ignore
                    )

                    await conn.execute(
                        """
                        INSERT INTO _timescaledb_catalog.chunk_index (
                            chunk_id, index_name, hypertable_id, hypertable_index_name
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (chunk.id, chunk_name, chunk.hypertable_id, name),
                    )
                    tg.create_task(execute(chunk_sql))

        if constraints:
            tg.create_task(
                execute(
                    SQL('ALTER TABLE {} {}').format(
                        Identifier(table),
                        SQL(',').join(
                            SQL('ADD CONSTRAINT {} {}').format(Identifier(name), sql)
                            for name, sql in constraints
                        ),
                    )
                )
            )

    async with TaskGroup() as tg:
        for table in all_tables:
            tg.create_task(load_task(table))

    async with db(True, autocommit=True) as conn:
        logging.info('Putting timescaledb into restore mode')
        await conn.execute('SELECT timescaledb_pre_restore()')

    async with TaskGroup() as tg:
        for table in all_tables:
            await index_task(table, tg)

    async with db(True, autocommit=True) as conn:
        logging.info('Putting timescaledb into operational mode')
        await conn.execute('SELECT timescaledb_post_restore()')


@psycopg_pool_open_decorator
async def main(mode: _Mode) -> None:
    exists = await ElementQuery.get_current_sequence_id() > 0
    if exists and input(
        'Database is not empty. Continue? (y/N): '
    ).strip().lower() not in {'y', 'yes'}:
        logging.error('Aborted')
        return

    await _load_tables(mode)

    logging.info('Updating statistics')
    async with db(True, autocommit=True) as conn:
        await conn.execute('ANALYZE')

    logging.info('Fixing sequence counters consistency')
    await MigrationService.fix_sequence_counters()

    logging.info('Running checkpoint')
    async with db(True, autocommit=True) as conn:
        await conn.execute('CHECKPOINT')


def main_cli() -> None:
    parser = ArgumentParser()
    parser.add_argument(
        '-m',
        '--mode',
        choices=get_args(_Mode),
        required=True,
    )
    args = parser.parse_args()
    asyncio.run(main(args.mode))


if __name__ == '__main__':
    main_cli()
