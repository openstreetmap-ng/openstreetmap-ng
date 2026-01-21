import asyncio
import logging
from argparse import ArgumentParser
from asyncio import Lock, Semaphore, TaskGroup, create_subprocess_shell
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
from app.db import (
    db,
    gather_table_constraints,
    gather_table_indexes,
    psycopg_pool_open_decorator,
)
from app.models.element import (
    TYPED_ELEMENT_ID_NODE_MAX,
    TYPED_ELEMENT_ID_RELATION_MAX,
    TYPED_ELEMENT_ID_WAY_MIN,
)
from app.queries.element_query import ElementQuery
from app.services.migration_service import MigrationService
from app.utils import calc_num_workers
from scripts.preload_convert import CHANGESETS_PARQUET_PATH, NOTES_PARQUET_PATH
from scripts.replication_download import replication_lock

_Mode = Literal['preload', 'replication']

# Sorted from heaviest to lightest tables
_Table = Literal[
    'element',
    'element_spatial',
    'changeset',
    'changeset_bounds',
    'note_comment',
    'note',
    'user',
    'element_spatial_watermark',
]


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
    if mode == 'preload' or table in {
        'note',
        'note_comment',
        'element_spatial',
        'element_spatial_watermark',
    }:
        path = _get_csv_path(table)

        # Skip optional data files
        if not path.is_file():
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
    maintenance_semaphore = Semaphore(maintenance_parallelism)
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
    async with db() as conn:
        for table in all_tables:
            indexes = await gather_table_indexes(conn, table)
            constraints = await gather_table_constraints(conn, table)
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
        async with maintenance_semaphore, db(True, autocommit=True) as conn:
            ts = monotonic()
            await conn.execute(sql)
            logging.debug('Executed %r in %.1fs', sql, monotonic() - ts)

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

            if not chunks and indexes:
                await conn.execute(
                    SQL('DROP INDEX {}').format(
                        SQL(', ').join(map(Identifier, indexes))
                    )
                )

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
                        sql
                        .as_string()
                        .replace(name, chunk_name)
                        .replace(
                            f'public.{table}', f'{chunk.schema_name}.{chunk.table_name}'
                        )  # type: ignore
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
    if mode == 'replication':
        if not (has_changesets := CHANGESETS_PARQUET_PATH.is_file()):
            logging.error(
                'Missing changesets file: %s (hint: `preload-convert changeset`)',
                CHANGESETS_PARQUET_PATH,
            )
        if not (has_notes := NOTES_PARQUET_PATH.is_file()):
            logging.warning(
                'Missing notes file: %s (hint: `preload-convert notes`)',
                NOTES_PARQUET_PATH,
            )

        if not has_changesets or (
            not has_notes
            and (input('Continue? (y/N): ').strip().lower() not in {'y', 'yes'})
        ):
            logging.error('Aborted')
            return

    exists = await ElementQuery.get_current_sequence_id() > 0
    if exists and input(
        'Database is not empty. Continue? (y/N): '
    ).strip().lower() not in {'y', 'yes'}:
        logging.error('Aborted')
        return

    with replication_lock() if mode == 'replication' else nullcontext():
        await _load_tables(mode)

    logging.info('Updating statistics')
    async with db(True, autocommit=True) as conn:
        await conn.execute('ANALYZE')

    if mode == 'replication':
        logging.info('Reconciling element/changeset tables')
        await MigrationService.cleanup_orphan_changesets_and_elements()

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
