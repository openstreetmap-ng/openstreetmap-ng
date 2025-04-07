import asyncio
import os
from argparse import ArgumentParser
from asyncio import TaskGroup, create_subprocess_shell
from asyncio.subprocess import PIPE, Process
from contextlib import asynccontextmanager
from io import TextIOWrapper
from pathlib import Path
from shlex import quote
from typing import Literal, get_args

from psycopg.abc import Query
from psycopg.sql import SQL, Identifier
from zstandard import ZstdDecompressor

from app.config import POSTGRES_URL, PRELOAD_DIR
from app.db import db, psycopg_pool_open_decorator
from app.queries.element_query import ElementQuery
from app.services.migration_service import MigrationService

_Mode = Literal['preload', 'replication']

_COPY_WORKERS = min(os.process_cpu_count() or 1, 8)  # type: ignore


def _get_csv_path(name: str) -> Path:
    return PRELOAD_DIR.joinpath(f'{name}.csv.zst')


def _get_csv_header(path: Path) -> str:
    with path.open('rb') as f:
        stream_reader = ZstdDecompressor().stream_reader(f)
        reader = TextIOWrapper(stream_reader)
        return reader.readline().strip()


@asynccontextmanager
async def _reduce_db_activity():
    async with db(True, autocommit=True) as conn:
        print('Pausing autovacuum and increasing checkpoint priority')
        await conn.execute('ALTER SYSTEM SET autovacuum = off')
        await conn.execute('ALTER SYSTEM SET checkpoint_completion_target = 0')
        await conn.execute('SELECT pg_reload_conf()')
    try:
        yield
    finally:
        async with db(True, autocommit=True) as conn:
            print('Restoring autovacuum and checkpoint settings')
            await conn.execute('ALTER SYSTEM RESET autovacuum')
            await conn.execute('ALTER SYSTEM RESET checkpoint_completion_target')
            await conn.execute('SELECT pg_reload_conf()')


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
            );
            """,
            (table, table),
        )
        return {name: SQL(sql) for name, sql in await cursor.fetchall()}


async def _gather_table_constraints(table: str) -> dict[tuple[str, str], SQL]:
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
            AND con.contype != 'p';  -- Exclude primary key constraints
            """,
            (table,),
        )
        return {(table, name): SQL(sql) for name, sql in await cursor.fetchall()}


async def _load_table(mode: _Mode, table: str, tg: TaskGroup) -> tuple[dict[str, SQL], dict[tuple[str, str], SQL]]:
    if mode == 'preload' or table in {'note', 'note_comment'}:
        path = _get_csv_path(table)

        # Replication supports optional data files
        if mode == 'replication' and not path.is_file():
            print(f'Skipped loading {table} table (source file not found)')
            return {}, {}

        copy_paths = [path.absolute().as_posix()]
        header = _get_csv_header(path)
        program = f'zstd -d --stdout {" ".join(f"{quote(p)}" for p in copy_paths)}'
    else:
        program = f'replication-convert {table}'
        proc = await create_subprocess_shell(f'{program} --header-only', stdout=PIPE)
        header = (await proc.communicate())[0].decode().strip()

    indexes = await _gather_table_indexes(table)
    assert indexes, f'No indexes found for {table} table'
    constraints = await _gather_table_constraints(table)

    # Drop constraints and indexes before loading
    print(f'Dropping {len(indexes)} indexes: {indexes!r}')
    print(f'Dropping {len(constraints)} constraints: {constraints!r}')
    async with db(True, autocommit=True) as conn:
        await conn.execute(SQL('DROP INDEX {}').format(SQL(',').join(map(Identifier, indexes))))

        for _, name in constraints:
            await conn.execute(SQL('ALTER TABLE {} DROP CONSTRAINT {}').format(Identifier(table), Identifier(name)))

    # Load the data
    columns = [f'"{c}"' for c in header.split(',')]
    proc: Process | None = None

    try:
        print(f'Populating {table} table ({len(columns)} columns)...')
        proc = await create_subprocess_shell(
            f'{program} | timescaledb-parallel-copy'
            ' --batch-size=100000'
            f' --columns={quote(",".join(columns))}'
            f' --connection={quote(POSTGRES_URL)}'
            f' --skip-header=true'
            ' --reporting-period=30s'
            f' --table={quote(table)}'
            f' --workers={_COPY_WORKERS}',
        )
        exit_code = await proc.wait()
        if exit_code:
            raise RuntimeError(f'Subprocess failed with exit code {exit_code}')

    except KeyboardInterrupt:
        if proc is not None:
            proc.terminate()

    # Fix replication-specific element issues
    async def replication_element_postprocess():
        async with db(True, autocommit=True) as conn:
            key = 'element_version_idx'
            print(f'Recreating index {key!r}')
            await conn.execute(indexes.pop(key))
            print(f'Updating {table} table statistics')
            await conn.execute(SQL('ANALYZE {}').format(Identifier(table)))

        print('Starting MigrationService tasks')
        tg.create_task(MigrationService.delete_duplicated_elements())
        tg.create_task(MigrationService.set_latest_elements())

    if mode == 'replication' and table == 'element':
        tg.create_task(replication_element_postprocess())

    return indexes, constraints


async def _load_tables(mode: _Mode) -> None:
    tables = ['user', 'changeset', 'element', 'note', 'note_comment']

    print('Truncating tables')
    async with db(True, autocommit=True) as conn:
        await conn.execute(SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(SQL(',').join(map(Identifier, tables))))

    indexes: dict[str, SQL] = {}
    constraints: dict[tuple[str, str], SQL] = {}

    async with TaskGroup() as tg:
        for table in tables:
            new_indexes, new_constraints = await _load_table(mode, table, tg)
            indexes.update(new_indexes)
            constraints.update(new_constraints)

    print(f'Recreating {len(indexes)} indexes and {len(constraints)} constraints')
    async with TaskGroup() as tg:

        async def execute(sql: Query) -> None:
            async with db(True, autocommit=True) as conn:
                await conn.execute(sql)

        for sql in indexes.values():
            tg.create_task(execute(sql))

        for (table, name), sql in constraints.items():
            tg.create_task(
                execute(SQL('ALTER TABLE {} ADD CONSTRAINT {} {}').format(Identifier(table), Identifier(name), sql))
            )


@psycopg_pool_open_decorator
async def main(mode: _Mode) -> None:
    exists = await ElementQuery.get_current_sequence_id() > 0
    if exists and input('Database is not empty. Continue? (y/N): ').strip().lower() not in {'y', 'yes'}:
        print('Aborted')
        return

    async with _reduce_db_activity():
        await _load_tables(mode)

        print('Vacuuming and updating statistics')
        async with db(True, autocommit=True) as conn:
            await conn.execute('VACUUM FREEZE ANALYZE' if mode == 'replication' else 'VACUUM ANALYZE')

        print('Fixing sequence counters consistency')
        await MigrationService.fix_sequence_counters()

        print('Performing final checkpoint')
        async with db(True, autocommit=True) as conn:
            await conn.execute('CHECKPOINT')

    print('Done! Done! Done!')


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
