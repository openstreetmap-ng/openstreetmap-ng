import asyncio
import os
from asyncio import TaskGroup, create_subprocess_shell
from asyncio.subprocess import Process
from shlex import quote

from sqlalchemy import Index, quoted_name, select, text
from sqlalchemy.orm import DeclarativeBase

from app.config import POSTGRES_URL, PRELOAD_DIR
from app.db import db, db_update_stats
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.db.user import User
from app.services.migration_service import MigrationService

_TIMESCALE_WORKERS = min(os.process_cpu_count() or 1, 8)


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
    async with db(True, no_transaction=True) as session:
        await session.execute(text(sql))


async def _load_table(table: type[DeclarativeBase], tg: TaskGroup) -> None:
    index_sqls: dict[quoted_name, str] = {}

    async with db(True) as session:
        for index in (arg for arg in table.__table_args__ if isinstance(arg, Index)):
            index_name = index.name
            assert index_name is not None
            print(f'Dropping index {index_name!r}')
            sql = await session.scalar(text(f'SELECT pg_get_indexdef({index_name!r}::regclass)'))
            index_sqls[index_name] = sql
            await session.execute(text(f'DROP INDEX {index_name}'))

    table_name = table.__tablename__
    copy_paths, header = _get_copy_paths_and_header(table_name)
    columns = tuple(f'"{c}"' for c in header.split(','))
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
            f' --workers={_TIMESCALE_WORKERS}',
        )
        exit_code = await proc.wait()
        if exit_code:
            raise RuntimeError(f'Subprocess failed with exit code {exit_code}')

    except KeyboardInterrupt:
        if proc is not None:
            proc.terminate()

    for key, sql in index_sqls.items():
        print(f'Recreating index {key!r}')
        tg.create_task(_index_task(sql))


async def _load_tables() -> None:
    tables = (User, Changeset, Element, ElementMember)

    async with db(True) as session:
        print('Truncating tables')
        await session.execute(
            text(f'TRUNCATE {",".join(f'"{table.__tablename__}"' for table in tables)} RESTART IDENTITY CASCADE')
        )

    async with TaskGroup() as tg:
        for table in tables:
            await _load_table(table, tg)


async def main() -> None:
    async with db(True) as session:
        if (
            await session.scalar(select(Element).limit(1))  #
            and not input('Database is not empty. Continue? (y/N): ').lower().startswith('y')
        ):
            print('Aborted')
            return

    await _load_tables()

    print('Updating statistics')
    await db_update_stats(vacuum=True)

    print('Fixing sequence counters consistency')
    await MigrationService.fix_sequence_counters()

    print('Fixing element next_sequence_id field')
    await MigrationService.fix_next_sequence_id()


if __name__ == '__main__':
    asyncio.run(main())
    print('Done! Done! Done!')
