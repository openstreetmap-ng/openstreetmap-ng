import asyncio
from asyncio import TaskGroup

from sqlalchemy import Index, quoted_name, select, text
from sqlalchemy.orm import DeclarativeBase

from app.config import PRELOAD_DIR
from app.db import db, db_update_stats
from app.models.db import *  # noqa: F403
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.db.user import User
from app.services.migration_service import MigrationService


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


async def _load_table(table: type[DeclarativeBase]) -> None:
    async with db(True) as session:
        # disable triggers
        await session.execute(text('SET session_replication_role TO replica'))

        # copy freeze requires truncate
        await session.execute(text(f'TRUNCATE {f'"{table.__tablename__}"'} RESTART IDENTITY CASCADE'))

        indexes = (arg for arg in table.__table_args__ if isinstance(arg, Index))
        index_sqls: dict[quoted_name, str] = {}
        for index in indexes:
            index_name = index.name
            assert index_name is not None
            print(f'Dropping index {index_name!r}')
            sql = await session.scalar(text(f'SELECT pg_get_indexdef({index_name!r}::regclass)'))
            index_sqls[index_name] = sql
            await session.execute(text(f'DROP INDEX {index_name}'))

        table_name = table.__tablename__
        copy_paths, header = _get_copy_paths_and_header(table_name)
        columns = tuple(f'"{c}"' for c in header.split(','))

        print(f'Populating {table_name} table ({len(columns)} columns)...')
        await session.execute(
            text(
                f'COPY "{table_name}" ({",".join(columns)}) '
                f"FROM PROGRAM 'zstd -d --stdout {' '.join(f'"{p}"' for p in copy_paths)}' "
                f'(FORMAT CSV, FREEZE, HEADER FALSE)'
            ),
        )

    async def index_task(sql: str) -> None:
        async with db() as session:
            await session.connection(execution_options={'isolation_level': 'AUTOCOMMIT'})
            await session.execute(text(sql))

    async with TaskGroup() as tg:
        for key, sql in index_sqls.items():
            print(f'Recreating index {key!r}')
            tg.create_task(index_task(sql))


async def load_tables() -> None:
    async with TaskGroup() as tg:
        for table in (User, Changeset, Element, ElementMember):
            tg.create_task(_load_table(table))


async def main() -> None:
    async with db(True) as session:
        if (
            await session.scalar(select(Element).limit(1))  #
            and not input('Database is not empty. Continue? (y/N): ').lower().startswith('y')
        ):
            print('Aborted')
            return

    await load_tables()

    print('Updating statistics')
    await db_update_stats()

    print('Fixing sequence counters consistency')
    await MigrationService.fix_sequence_counters()


if __name__ == '__main__':
    asyncio.run(main())
    print('Done! Done! Done!')
