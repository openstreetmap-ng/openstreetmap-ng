import asyncio
from asyncio import TaskGroup
from shlex import quote

from psycopg.abc import Query
from psycopg.sql import SQL, Identifier, Literal

from app.config import PRELOAD_DIR
from app.db import db, psycopg_pool_open_decorator
from app.queries.element_query import ElementQuery
from app.services.migration_service import MigrationService
from scripts.preload_load import gather_table_constraints, gather_table_indexes, get_csv_header, get_csv_path


def _get_copy_paths_and_header(table: str) -> tuple[list[str], str]:
    output = PRELOAD_DIR.joinpath(table)
    copy_paths = [
        p.absolute().as_posix()
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
    if table in {'note', 'note_comment'}:
        path = get_csv_path(table)
        if not path.is_file():
            print(f'Skipped loading {table} table (source file not found)')
            return

        copy_paths = [path.absolute().as_posix()]
        header = get_csv_header(path)
        source_has_header = True
    else:
        copy_paths, header = _get_copy_paths_and_header(table)
        source_has_header = False

    indexes = await gather_table_indexes(table)
    assert indexes, f'No indexes found for {table} table'
    constraints = await gather_table_constraints(table)

    async with db(True) as conn:
        # Drop constraints and indexes before loading
        print(f'Dropping {len(indexes)} indexes: {indexes!r}')
        await conn.execute(SQL('DROP INDEX {}').format(SQL(',').join(map(Identifier, indexes))))

        print(f'Dropping {len(constraints)} constraints: {constraints!r}')
        for name in constraints:
            await conn.execute(SQL('ALTER TABLE {} DROP CONSTRAINT {}').format(Identifier(table), Identifier(name)))

        # Truncate table again (required by FREEZE)
        await conn.execute(SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(Identifier(table)))

        # Load the data
        columns = header.split(',')
        program = f'zstd -d --stdout {" ".join(f"{quote(p)}" for p in copy_paths)}'

        print(f'Populating {table} table ({len(columns)} columns)...')
        await conn.execute(
            SQL("""
                COPY {table} ({columns})
                FROM PROGRAM {program}
                (FORMAT CSV, FREEZE, HEADER {header})
            """).format(
                table=Identifier(table),
                columns=SQL(',').join(map(Identifier, columns)),
                program=Literal(program),
                header=SQL('TRUE' if source_has_header else 'FALSE'),
            ),
        )

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
            await _load_table(table, tg)


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
