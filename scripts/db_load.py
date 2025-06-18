import asyncio
import logging
from argparse import ArgumentParser
from asyncio import Lock, Semaphore, TaskGroup, create_subprocess_shell
from asyncio.subprocess import PIPE, Process
from contextlib import nullcontext
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
    'user',
    'changeset',
    'changeset_bounds',
    'changeset_comment',
    'element',
    'note',
    'note_comment',
]
# _ConstraintType = Literal['f', 'p', 'u', 'c']

_FIRST_TABLES: tuple[_Table, ...] = ('user',)
_NEXT_TABLES: dict[_Table, tuple[_Table, ...]] = {
    'user': ('changeset', 'note'),
    'changeset': ('changeset_bounds', 'changeset_comment', 'element'),
    'note': ('note_comment',),
}

_TABLE_LOCK = Lock()
_NUM_WORKERS_COPY = calc_num_workers(max=8)
_INDEX_SEMAPHORE = Semaphore(2)


def _get_csv_path(table: _Table) -> Path:
    return PRELOAD_DIR.joinpath(f'{table}.csv.zst')


def _get_csv_header(path: Path) -> str:
    with path.open('rb') as f:
        stream_reader = ZstdDecompressor().stream_reader(f)
        reader = TextIOWrapper(stream_reader)
        return reader.readline().strip()


async def _gather_table_indexes(table: _Table) -> dict[str, SQL]:
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


async def _drop_table_indexes(table: _Table, indexes: dict[str, SQL]) -> None:
    if not indexes:
        return

    async with db(True, autocommit=True) as conn:
        logging.info(
            'Dropping %d indexes for %s: %r',
            len(indexes),
            table,
            indexes,
        )
        await conn.execute(
            SQL('DROP INDEX {}').format(SQL(',').join(map(Identifier, indexes)))
        )


async def _gather_table_identity(table: _Table) -> list[str]:
    async with db() as conn:
        cursor = await conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = %s
            AND is_identity = 'YES'
            """,
            (table,),
        )
        return [c for (c,) in await cursor.fetchall()]


async def _drop_table_identity(table: _Table, identity: list[str]) -> None:
    if not identity:
        return

    async with db(True, autocommit=True) as conn:
        logging.debug(
            'Dropping %d identity columns for %s: %r',
            len(identity),
            table,
            identity,
        )
        await conn.execute(
            SQL('ALTER TABLE {} {}').format(
                Identifier(table),
                SQL(',').join(
                    SQL('ALTER COLUMN {} DROP IDENTITY').format(Identifier(name))
                    for name in identity
                ),
            )
        )


async def _gather_table_constraints(table: _Table) -> list[tuple[str, SQL]]:
    async with db() as conn:
        cursor = await conn.execute(
            """
            SELECT con.conname, pg_get_constraintdef(con.oid)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE rel.relname = %s
            AND nsp.nspname = 'public'
            ORDER BY
                CASE con.contype
                    WHEN 'f' THEN 1  -- Foreign keys
                    WHEN 'c' THEN 2  -- Check constraints
                    WHEN 'u' THEN 3  -- Unique constraints
                    WHEN 'p' THEN 4  -- Primary keys
                    ELSE 5
                END
            """,
            (table,),
        )
        return [(name, SQL(sql)) for name, sql in await cursor.fetchall()]


async def _drop_table_constraints(
    table: _Table, constraints: list[tuple[str, SQL]]
) -> None:
    if not constraints:
        return

    async with db(True, autocommit=True) as conn:
        logging.info(
            'Dropping %d constraints for %s: %r',
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


async def _create_table_constraints_and_identity(
    table: _Table, constraints: list[tuple[str, SQL]], identity: list[str]
) -> None:
    async with db(True, autocommit=True) as conn:
        if constraints:
            await conn.execute(
                SQL('ALTER TABLE {} {}').format(
                    Identifier(table),
                    SQL(',').join(
                        SQL('ADD CONSTRAINT {} {}').format(Identifier(name), sql)
                        for name, sql in constraints
                    ),
                )
            )

        if identity:
            await conn.execute(
                SQL('ALTER TABLE {} {}').format(
                    Identifier(table),
                    SQL(',').join(
                        SQL('ALTER COLUMN {} ADD GENERATED ALWAYS AS IDENTITY').format(
                            Identifier(name)
                        )
                        for name in identity
                    ),
                )
            )


async def _load_table(mode: _Mode, table: _Table) -> None:
    if table in {'changeset_comment'}:
        return

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

    async with _TABLE_LOCK if mode == 'replication' else nullcontext():
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


async def _load_tables(mode: _Mode) -> None:
    all_tables = get_args(_Table)

    logging.info('Truncating tables: %r', all_tables)
    async with db(True, autocommit=True) as conn:
        await conn.execute(
            SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(
                SQL(',').join(map(Identifier, all_tables))
            )
        )

    logging.info('Gathering indexes and constraints')
    table_data: dict[
        _Table,
        tuple[
            dict[str, SQL],  # indexes
            list[str],  # identity
            list[tuple[str, SQL]],  # constraints
        ],
    ]
    table_data = {}
    for table in all_tables:
        indexes = await _gather_table_indexes(table)
        assert indexes, f'No indexes found for {table} table'
        identity = await _gather_table_identity(table)
        constraints = await _gather_table_constraints(table)
        table_data[table] = (indexes, identity, constraints)

    async with db(True, autocommit=True) as conn:
        for table in all_tables[::-1]:
            indexes, identity, constraints = table_data[table]
            await _drop_table_identity(table, identity)
            await _drop_table_constraints(table, constraints)
            await _drop_table_indexes(table, indexes)

    async with TaskGroup() as tg:

        async def create_index(sql: Query) -> None:
            async with _INDEX_SEMAPHORE, db(True, autocommit=True) as conn:
                ts = monotonic()
                await conn.execute(sql)
                logging.debug('Executed %r in %.1fs', sql, monotonic() - ts)

        async def task(table: _Table) -> None:
            await _load_table(mode, table)

            logging.info('Recreating indexes and constraints')
            indexes, identity, constraints = table_data[table]

            # Create indexes
            for sql in indexes.values():
                tg.create_task(create_index(sql))

            # Create constraints and identity
            tg.create_task(
                _create_table_constraints_and_identity(table, constraints, identity)
            )

            # Recurse
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
