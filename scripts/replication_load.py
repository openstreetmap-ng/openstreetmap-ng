import asyncio
import os
from asyncio import TaskGroup, create_subprocess_shell
from asyncio.subprocess import Process
from shlex import quote

from psycopg.abc import Query
from psycopg.sql import SQL, Identifier

from app.config import POSTGRES_URL, PRELOAD_DIR
from app.db import db, psycopg_pool_open_decorator
from app.queries.element_query import ElementQuery
from app.services.migration_service import MigrationService
from scripts.preload_load import gather_table_constraints, gather_table_indexes
from scripts.preload_load import load_table as preload_load_table

_NUM_COPY_WORKERS = min(os.process_cpu_count() or 1, 8)


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


async def _sql_execute(sql: Query) -> None:
    async with db(True, autocommit=True) as conn:
        await conn.execute(sql)


async def _load_table(table: str, tg: TaskGroup) -> None:
    indexes = await gather_table_indexes(table)
    assert indexes, f'No indexes found for {table} table'
    constraints = await gather_table_constraints(table)

    # Drop constraints and indexes before loading
    async with db(True, autocommit=True) as conn:
        print(f'Dropping {len(indexes)} indexes: {indexes!r}')
        await conn.execute(SQL('DROP INDEX {}').format(SQL(',').join(map(Identifier, indexes))))

        print(f'Dropping {len(constraints)} constraints: {constraints!r}')
        for name in constraints:
            await conn.execute(SQL('ALTER TABLE {} DROP CONSTRAINT {}').format(Identifier(table), Identifier(name)))

    # Load the data
    copy_paths, header = _get_copy_paths_and_header(table)
    columns = [f'"{c}"' for c in header.split(',')]
    proc: Process | None = None

    try:
        print(f'Populating {table} table ({len(columns)} columns)...')
        proc = await create_subprocess_shell(
            f'zstd -d --stdout {" ".join(f"{quote(p)}" for p in copy_paths)}'
            ' | timescaledb-parallel-copy'
            ' --batch-size=100000'
            f' --columns={quote(",".join(columns))}'
            f' --connection={quote(POSTGRES_URL)}'
            ' --skip-header=false'
            ' --reporting-period=30s'
            f' --table={quote(table)}'
            f' --workers={_NUM_COPY_WORKERS}',
        )
        exit_code = await proc.wait()
        if exit_code:
            raise RuntimeError(f'Subprocess failed with exit code {exit_code}')

    except KeyboardInterrupt:
        if proc is not None:
            proc.terminate()

    if table == 'element':
        key = 'element_version_idx'
        print(f'Recreating index {key!r}')
        await _sql_execute(indexes.pop(key))
        print('Deleting duplicated element rows')
        await MigrationService.fix_duplicated_element_version()
        print('Fixing element.next_sequence_id field')
        await MigrationService.fix_next_sequence_id()

    print(f'Recreating {len(indexes)} indexes')
    for sql in indexes.values():
        tg.create_task(_sql_execute(sql))

    print(f'Recreating {len(constraints)} constraints')
    for name, sql in constraints.items():
        tg.create_task(
            _sql_execute(SQL('ALTER TABLE {} ADD CONSTRAINT {} {}').format(Identifier(table), Identifier(name), sql))
        )


async def _load_tables() -> None:
    tables = ('user', 'changeset', 'element', 'note', 'note_comment')

    async with db(True, autocommit=True) as conn:
        print('Truncating tables')
        await conn.execute(SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(SQL(',').join(map(Identifier, tables))))

    async with TaskGroup() as tg:
        for table in tables:
            await (
                preload_load_table
                if table in {'note', 'note_comment'}  #
                else _load_table
            )(table, tg)


@psycopg_pool_open_decorator
async def main() -> None:
    exists = await ElementQuery.get_current_sequence_id() > 0
    if exists and not input('Database is not empty. Continue? (y/N): ').lower().startswith('y'):
        print('Aborted')
        return

    await _load_tables()

    print('Vacuuming and updating statistics')
    async with db(True, autocommit=True) as conn:
        await conn.execute('VACUUM FREEZE ANALYZE')

    print('Fixing sequence counters consistency')
    await MigrationService.fix_sequence_counters()

    print('Done! Done! Done!')


if __name__ == '__main__':
    asyncio.run(main())
