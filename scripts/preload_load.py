import asyncio
import os
from asyncio import TaskGroup, create_subprocess_shell
from asyncio.subprocess import Process
from io import TextIOWrapper
from pathlib import Path
from shlex import quote

from psycopg.abc import Query
from psycopg.sql import SQL, Identifier
from zstandard import ZstdDecompressor

from app.config import POSTGRES_URL, PRELOAD_DIR
from app.db import db, db_update_stats, psycopg_pool_open_decorator
from app.services.migration_service import MigrationService

_COPY_WORKERS = min(os.process_cpu_count() or 1, 8)


def _get_csv_path(name: str) -> Path:
    p = PRELOAD_DIR.joinpath(f'{name}.csv.zst')
    if not p.is_file():
        raise FileNotFoundError(f'File not found: {p}')
    return p


def _get_csv_header(path: Path) -> str:
    with path.open('rb') as f:
        stream_reader = ZstdDecompressor().stream_reader(f)
        reader = TextIOWrapper(stream_reader)
        return reader.readline().strip()


async def _sql_execute(sql: Query) -> None:
    async with db(True, autocommit=True) as conn:
        await conn.execute(sql)


async def _gather_table_constraints(table: str) -> dict[str, SQL]:
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
        return {name: SQL(sql) for name, sql in await cursor.fetchall()}


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


async def _load_table(table: str, tg: TaskGroup) -> None:
    indexes = await _gather_table_indexes(table)
    assert indexes, f'No indexes found for {table} table'
    constraints = await _gather_table_constraints(table)

    # Drop constraints and indexes before loading
    async with db(True, autocommit=True) as conn:
        print(f'Dropping {len(indexes)} indexes: {indexes!r}')
        await conn.execute(SQL('DROP INDEX {}').format(SQL(',').join(map(Identifier, indexes))))

        print(f'Dropping {len(constraints)} constraints: {constraints!r}')
        for name in constraints:
            await conn.execute(SQL('ALTER TABLE {} DROP CONSTRAINT {}').format(Identifier(table), Identifier(name)))

    # Load the data
    path = _get_csv_path(table)
    header = _get_csv_header(path)
    columns = [f'"{c}"' for c in header.split(',')]
    proc: Process | None = None

    try:
        print(f'Populating {table} table ({len(columns)} columns)...')
        proc = await create_subprocess_shell(
            f'zstd -d --stdout {quote(path.absolute().as_posix())}'
            ' | timescaledb-parallel-copy'
            ' --batch-size=100000'
            f' --columns={quote(",".join(columns))}'
            f' --connection={quote(POSTGRES_URL)}'
            ' --skip-header=true'
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

    print(f'Recreating {len(indexes)} indexes')
    for sql in indexes.values():
        tg.create_task(_sql_execute(sql))

    print(f'Recreating {len(constraints)} constraints')
    for name, sql in constraints.items():
        tg.create_task(
            _sql_execute(SQL('ALTER TABLE {} ADD CONSTRAINT {} {}').format(Identifier(table), Identifier(name), sql))
        )


async def _load_tables() -> None:
    tables = ('user', 'note', 'note_comment', 'changeset', 'element')

    async with db(True, autocommit=True) as conn:
        print('Truncating tables')
        await conn.execute(SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(SQL(',').join(map(Identifier, tables))))

    async with TaskGroup() as tg:
        for table in tables:
            await _load_table(table, tg)


@psycopg_pool_open_decorator
async def main() -> None:
    async with db() as conn:
        cursor = await conn.execute('SELECT 1 FROM element LIMIT 1')
        exists = await cursor.fetchone() is not None

    if exists and not input('Database is not empty. Continue? (y/N): ').lower().startswith('y'):
        print('Aborted')
        return

    await _load_tables()

    print('Updating statistics')
    await db_update_stats(vacuum=True)

    print('Fixing sequence counters consistency')
    await MigrationService.fix_sequence_counters()


if __name__ == '__main__':
    asyncio.run(main())
    print('Done! Done! Done!')
