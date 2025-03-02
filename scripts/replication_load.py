import asyncio
import os
from asyncio import TaskGroup, create_subprocess_shell
from asyncio.subprocess import Process
from shlex import quote

from psycopg.sql import SQL, Identifier
from sqlalchemy.orm import DeclarativeBase

from app.config import POSTGRES_URL, PRELOAD_DIR
from app.db import db2, db_update_stats, psycopg_pool_open_decorator
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.db.user import User
from app.services.migration_service import MigrationService

_COPY_WORKERS = min(os.process_cpu_count() or 1, 8)


def _get_copy_paths_and_header(table: str) -> tuple[list[str], str]:
    output = PRELOAD_DIR.joinpath(table)
    copy_paths = [
        p.as_posix()
        for p in sorted(
            output.glob('*.csv.zst'),
            key=lambda p: int(p.with_suffix('').stem.split('_', 1)[1]),
        )
    ]
    header = output.joinpath('header.csv').read_text()
    return copy_paths, header


async def _index_task(sql: str) -> None:
    async with db2(True, autocommit=True) as conn:
        await conn.execute(sql)  # type: ignore


async def _load_table(table: type[DeclarativeBase], tg: TaskGroup) -> None:
    table_name = table.__tablename__

    async with db2(True, autocommit=True) as conn:
        # drop indexes that are not used by any constraint
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
            (table_name, table_name),
        )
        index_sqls: dict[str, str] = dict(await cursor.fetchall())
        assert index_sqls, f'No indexes found for {table_name} table'
        print(f'Dropping indexes {index_sqls!r}')
        await conn.execute(SQL('DROP INDEX {0}').format(SQL(',').join(map(Identifier, index_sqls))))

    copy_paths, header = _get_copy_paths_and_header(table_name)
    columns = [f'"{c}"' for c in header.split(',')]
    proc: Process | None = None

    try:
        print(f'Populating {table_name} table ({len(columns)} columns)...')
        proc = await create_subprocess_shell(
            f'zstd -d --stdout {" ".join(f"{quote(p)}" for p in copy_paths)}'
            ' | timescaledb-parallel-copy'
            ' --batch-size=100000'
            f' --columns={quote(",".join(columns))}'
            f' --connection={quote(POSTGRES_URL)}'
            ' --skip-header=false'
            ' --reporting-period=30s'
            f' --table={quote(table_name)}'
            f' --workers={_COPY_WORKERS}',
        )
        exit_code = await proc.wait()
        if exit_code:
            raise RuntimeError(f'Subprocess failed with exit code {exit_code}')

    except KeyboardInterrupt:
        if proc is not None:
            proc.terminate()

    async def postprocess() -> None:
        if table is User:
            key = 'element_version_idx'
            print(f'Recreating index {key!r}')
            await _index_task(index_sqls.pop(key))
            print('Fixing element next_sequence_id field')
            await MigrationService.fix_next_sequence_id()

        print('Recreating indexes')
        for sql in index_sqls.values():
            tg.create_task(_index_task(sql))

    tg.create_task(postprocess())


async def _load_tables() -> None:
    tables = (User, Changeset, Element, ElementMember)

    async with db2(True, autocommit=True) as conn:
        print('Truncating tables')
        await conn.execute(
            SQL('TRUNCATE {tables} RESTART IDENTITY CASCADE').format(
                tables=SQL(',').join(Identifier(table.__tablename__) for table in tables)
            )
        )

    async with TaskGroup() as tg:
        for table in tables:
            await _load_table(table, tg)


@psycopg_pool_open_decorator
async def main() -> None:
    async with db2() as conn:
        cursor = await conn.execute('SELECT 1 FROM element ORDER BY sequence_id LIMIT 1')
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
