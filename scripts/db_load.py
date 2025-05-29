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

_PARALLELISM = min(calc_num_workers(), 8)


def _get_csv_path(name: str) -> Path:
    return PRELOAD_DIR.joinpath(f'{name}.csv.zst')


def _get_csv_header(path: Path) -> str:
    with path.open('rb') as f:
        stream_reader = ZstdDecompressor().stream_reader(f)
        reader = TextIOWrapper(stream_reader)
        return reader.readline().strip()


async def _gather_table_indexes(table: str) -> dict[str, SQL]:
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


async def _gather_table_constraints(table: str) -> list[tuple[str, SQL]]:
    """Gather all foreign key constraints for a table."""
    async with db() as conn:
        cursor = await conn.execute(
            """
            SELECT con.conname, pg_get_constraintdef(con.oid)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE rel.relname = %s
            AND nsp.nspname = 'public'
            AND con.contype != 'p'  -- Exclude primary key constraints
            AND con.conname NOT LIKE '%%_id_not_null'
            """,
            (table,),
        )
        return [(name, SQL(sql)) for name, sql in await cursor.fetchall()]


async def _load_table(
    mode: _Mode,
    table: str,
    indexes: dict[str, SQL],
    constraints: dict[str, list[tuple[str, SQL]]],
    tg: TaskGroup,
) -> None:
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

    this_indexes = await _gather_table_indexes(table)
    assert this_indexes, f'No indexes found for {table} table'
    this_constraints = await _gather_table_constraints(table)

    # Drop constraints and indexes before loading
    async with db(True, autocommit=True) as conn:
        logging.info('Dropping %d indexes: %r', len(this_indexes), this_indexes)
        indexes.update(this_indexes)
        await conn.execute(
            SQL('DROP INDEX {}').format(SQL(',').join(map(Identifier, this_indexes)))
        )

        if this_constraints:
            logging.info(
                'Dropping %d constraints: %r', len(this_constraints), this_constraints
            )
            constraints[table] = this_constraints
            await conn.execute(
                SQL('ALTER TABLE {} {}').format(
                    Identifier(table),
                    SQL(',').join(
                        SQL('DROP CONSTRAINT {}').format(Identifier(name))
                        for name, _ in this_constraints
                    ),
                )
            )

    # Delete variables to avoid accidental use
    del this_indexes, this_constraints

    # Load the data
    columns = [f'"{c}"' for c in header.split(',')]
    proc: Process | None = None

    try:
        logging.info('Populating %s table (%d columns)...', table, len(columns))
        proc = await create_subprocess_shell(
            f'{program} | timescaledb-parallel-copy'
            ' --batch-size=100000'
            f' --columns={quote(",".join(columns))}'
            f' --connection={quote(POSTGRES_URL)}'
            f' --skip-header=true'
            ' --reporting-period=30s'
            f' --table={quote(table)}'
            f' --workers={_PARALLELISM}',
        )
        exit_code = await proc.wait()
        if exit_code:
            raise RuntimeError(f'Subprocess failed with exit code {exit_code}')

    except KeyboardInterrupt:
        if proc is not None:
            proc.terminate()

    async def element_postprocess():
        async with db(True, autocommit=True) as conn:
            key = 'element_version_idx'
            logging.info('Recreating index %r', key)
            await conn.execute(indexes.pop(key))
            logging.info('Updating table statistics')
            await conn.execute('ANALYZE element')

        logging.info('Marking latest elements')
        await MigrationService.mark_latest_elements()

    async def note_comment_postprocess():
        async with db(True, autocommit=True) as conn:
            key = 'note_comment_note_id_idx'
            logging.info('Recreating index %r', key)
            await conn.execute(indexes.pop(key))
            logging.info('Updating table statistics')
            await conn.execute('ANALYZE note, note_comment')

        logging.info('Deleting notes without comments')
        await MigrationService.delete_notes_without_comments()

    # Optional postprocessing
    if mode == 'replication':
        if table == 'element':
            tg.create_task(element_postprocess())
        elif table == 'note_comment':
            tg.create_task(note_comment_postprocess())


async def _load_tables(mode: _Mode) -> None:
    tables = ['user', 'changeset', 'element', 'note', 'note_comment']

    logging.info('Truncating tables')
    async with db(True, autocommit=True) as conn:
        await conn.execute(
            SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(
                SQL(',').join(map(Identifier, tables))
            )
        )

    indexes: dict[str, SQL] = {}
    constraints: dict[str, list[tuple[str, SQL]]] = {}

    async with TaskGroup() as tg:
        for table in tables:
            await _load_table(mode, table, indexes, constraints, tg)

    logging.info(
        'Recreating %d indexes and %d constraints',
        len(indexes),
        sum(len(c) for c in constraints.values()),
    )
    async with TaskGroup() as tg:
        semaphore = Semaphore(_PARALLELISM)

        async def execute(sql: Query) -> None:
            async with semaphore, db(True, autocommit=True) as conn:
                ts = monotonic()
                await conn.execute(sql)
                logging.debug('Executed %r in %.1fs', sql, monotonic() - ts)

        for sql in indexes.values():
            tg.create_task(execute(sql))

        for table, this_constraints in constraints.items():
            tg.create_task(
                execute(
                    SQL('ALTER TABLE {} {}').format(
                        Identifier(table),
                        SQL(',').join(
                            SQL('ADD CONSTRAINT {} {}').format(Identifier(name), sql)
                            for name, sql in this_constraints
                        ),
                    )
                )
            )


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
