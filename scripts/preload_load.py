import asyncio
import subprocess
from asyncio import TaskGroup
from functools import cache
from pathlib import Path
from subprocess import Popen

from sqlalchemy import Index, quoted_name, select, text
from sqlalchemy.orm import DeclarativeBase

from app.config import PRELOAD_DIR
from app.db import db, db_update_stats
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.models.db.user import User
from app.services.migration_service import MigrationService


@cache
def _get_csv_path(name: str) -> Path:
    p = PRELOAD_DIR.joinpath(f'{name}.csv.zst')
    if not p.is_file():
        raise FileNotFoundError(f'File not found: {p}')
    return p


@cache
def _get_csv_header(path: Path) -> str:
    with Popen(
        ('zstd', '-d', '--stdout', str(path)),
        stdout=subprocess.PIPE,
    ) as proc:
        assert proc.stdout is not None
        line = proc.stdout.readline().decode().strip()
        proc.terminate()
    return line


async def _index_task(sql: str) -> None:
    async with db(True, no_transaction=True) as session:
        await session.execute(text(sql))


async def _load_table(table: type[DeclarativeBase], tg: TaskGroup) -> None:
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
        path = _get_csv_path(table_name)
        header = _get_csv_header(path)
        columns = tuple(f'"{c}"' for c in header.split(','))

        print(f'Populating {table_name} table ({len(columns)} columns)...')
        await session.execute(
            text(
                f'COPY "{table_name}" ({",".join(columns)}) '
                f'FROM PROGRAM \'zstd -d --stdout "{path.absolute()}"\' '
                f'(FORMAT CSV, FREEZE, HEADER TRUE)'
            ),
        )

    for key, sql in index_sqls.items():
        print(f'Recreating index {key!r}')
        tg.create_task(_index_task(sql))


async def _load_tables() -> None:
    tables = (User, Changeset, Element, ElementMember, Note, NoteComment)

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
    await db_update_stats()

    print('Fixing sequence counters consistency')
    await MigrationService.fix_sequence_counters()


if __name__ == '__main__':
    asyncio.run(main())
    print('Done! Done! Done!')
