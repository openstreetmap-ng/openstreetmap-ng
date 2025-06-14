import asyncio
import logging
from argparse import ArgumentParser
from asyncio import Semaphore, TaskGroup, create_subprocess_shell
from asyncio.subprocess import PIPE, Process
from io import TextIOWrapper
from pathlib import Path
from shlex import quote
from time import monotonic
from typing import Literal, get_args

from psycopg.abc import Query
from psycopg.sql import SQL, Identifier
from zstandard import ZstdDecompressor

from app.config import POSTGRES_URL, PRELOAD_DIR
from app.db import db, psycopg_pool_open_decorator
from app.queries.element_query import ElementQuery
from app.services.migration_service import MigrationService
from app.utils import calc_num_workers

_Mode = Literal['preload', 'replication']
_Table = Literal[
    'user', 'changeset', 'changeset_bounds', 'element', 'note', 'note_comment'
]

_FIRST_TABLES: tuple[_Table, ...] = ('user',)
_NEXT_TABLES: dict[_Table, tuple[_Table, ...]] = {
    'user': ('changeset', 'note'),
    'changeset': ('changeset_bounds', 'element'),
    'note': ('note_comment',),
}

_NUM_WORKERS_COPY = calc_num_workers(max=8)
_INDEX_SEMAPHORE = Semaphore(calc_num_workers(0.5, min=2))


def _get_csv_path(table: _Table) -> Path:
    return PRELOAD_DIR.joinpath(f'{table}.csv.zst')


def _get_csv_header(path: Path) -> str:
    with path.open('rb') as f:
        stream_reader = ZstdDecompressor().stream_reader(f)
        reader = TextIOWrapper(stream_reader)
        return reader.readline().strip()


async def _gather_table_indexes(table: _Table) -> dict[str, SQL]:
    """Gather all non-constraint indexes for a table."""
    async with db() as conn:
        cursor = await conn.execute(
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
        )
        return {name: SQL(sql) for name, sql in await cursor.fetchall()}


async def _gather_table_constraints(table: _Table) -> list[tuple[str, SQL]]:
    """Gather all foreign key constraints for a table."""
    async with db() as conn:
        cursor = await conn.execute(
            SQL("""
            SELECT con.conname, pg_get_constraintdef(con.oid)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE rel.relname = %s
            AND nsp.nspname = 'public' {}
            """).format(
                SQL(
                    """
                    AND con.contype != 'p'  -- Exclude primary key constraints
                    AND con.conname NOT LIKE '%%_id_not_null'
                    """
                    if table != 'element'
                    else ''
                )
            ),
            (table,),
        )
        return [(name, SQL(sql)) for name, sql in await cursor.fetchall()]


async def _load_table(mode: _Mode, table: _Table, tg: TaskGroup) -> None:
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

    indexes = await _gather_table_indexes(table)
    assert indexes, f'No indexes found for {table} table'
    constraints = await _gather_table_constraints(table)

    # Drop indexes and constraints before loading
    async with db(True, autocommit=True) as conn:
        logging.info('Dropping %d indexes: %r', len(indexes), indexes)
        await conn.execute(
            SQL('DROP INDEX {}').format(SQL(',').join(map(Identifier, indexes)))
        )

        if constraints:
            logging.info('Dropping %d constraints: %r', len(constraints), constraints)
            await conn.execute(
                SQL('ALTER TABLE {} {}').format(
                    Identifier(table),
                    SQL(',').join(
                        SQL('DROP CONSTRAINT {}').format(Identifier(name))
                        for name, _ in constraints
                    ),
                )
            )

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

    # Recreate indexes and constraints after loading
    async def index_postprocess():
        logging.info('Recreating indexes and constraints')

        async def execute(sql: Query) -> None:
            async with _INDEX_SEMAPHORE, db(True, autocommit=True) as conn:
                ts = monotonic()
                await conn.execute(sql)
                logging.debug('Executed %r in %.1fs', sql, monotonic() - ts)

        for sql in indexes.values():
            tg.create_task(execute(sql))

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

    # Begin postprocessing
    tg.create_task(index_postprocess())


async def _load_tables(mode: _Mode) -> None:
    logging.info('Truncating tables')
    async with db(True, autocommit=True) as conn:
        await conn.execute(
            SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(
                SQL(',').join(map(Identifier, get_args(_Table)))
            )
        )

    async with TaskGroup() as tg:

        async def task(table: _Table) -> None:
            await _load_table(mode, table, tg)
            for next_table in _NEXT_TABLES.get(table, ()):
                tg.create_task(task(next_table))

        for first_table in _FIRST_TABLES:
            tg.create_task(task(first_table))


@psycopg_pool_open_decorator
async def main(mode: _Mode) -> None:
    exists = await ElementQuery.get_current_sequence_id() > 0
    if exists and input(
        'Database is not empty. Continue? (y/N): '
    ).strip().lower() not in {'y', 'yes'}:
        logging.error('Aborted')
        return

    await _load_tables(mode)

    logging.info('Vacuuming and updating statistics')
    async with db(True, autocommit=True) as conn:
        await conn.execute('VACUUM ANALYZE')

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
