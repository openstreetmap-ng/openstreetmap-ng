import gc
import pathlib
import subprocess
from subprocess import Popen

import anyio
from anyio import create_task_group
from sqlalchemy import Index, select, text

from app.config import PRELOAD_DIR
from app.db import db, db_commit, db_update_stats
from app.models.db import *  # noqa: F403
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.user import User
from app.services.migration_service import MigrationService

user_csv_path = pathlib.Path(PRELOAD_DIR / 'user.csv.zst')
changeset_csv_path = pathlib.Path(PRELOAD_DIR / 'changeset.csv.zst')
element_csv_path = pathlib.Path(PRELOAD_DIR / 'element.csv.zst')

for p in (user_csv_path, changeset_csv_path, element_csv_path):
    if not p.is_file():
        raise FileNotFoundError(f'File not found: {p}')

# freeze all gc objects before starting for improved performance
gc.collect()
gc.freeze()
gc.disable()


def get_csv_header(path: pathlib.Path) -> str:
    with Popen(
        (  # noqa: S603
            'zstd',
            '-d',
            '--stdout',
            str(path),
        ),
        stdout=subprocess.PIPE,
    ) as proc:
        line = proc.stdout.readline().decode().strip()
        proc.kill()
    return line


async def main() -> None:
    async with db_commit() as session:
        if await session.scalar(select(Element).limit(1)):  # noqa: SIM102
            if input('Database is not empty. Continue? (y/N): ').lower() != 'y':
                print('Aborted')
                return

        # copy freeze requires truncate
        print('Truncating')
        tables = (Element, Changeset, User)
        table_names = ', '.join(f'"{t.__tablename__}"' for t in tables)
        await session.execute(text(f'TRUNCATE {table_names} RESTART IDENTITY CASCADE'))

        print('Disabling triggers')
        await session.execute(text('SET session_replication_role TO replica'))

        # discover indexes on the element table
        indexes = (
            arg
            for table in tables  #
            for arg in table.__table_args__
            if isinstance(arg, Index)
        )
        index_create_sqls: list[str] = []

        for index in indexes:
            print(f'Dropping index {index.name!r}')
            create_sql = await session.scalar(text(f'SELECT pg_get_indexdef({index.name!r}::regclass)'))
            index_create_sqls.append(create_sql)
            await session.execute(text(f'DROP INDEX {index.name}'))

        if not index_create_sqls:
            raise AssertionError('Database is in a bad state (run `dev-clean` to reset)')

        header = get_csv_header(user_csv_path)
        columns = tuple(f'"{c}"' for c in header.split(','))
        print(f'Populating user table ({len(columns)} columns)...')
        await session.execute(
            text(
                f'COPY "{User.__tablename__}" ({", ".join(columns)}) '
                f"FROM PROGRAM 'zstd -d --stdout \"{user_csv_path.absolute()}\"' "
                f'(FORMAT CSV, FREEZE, HEADER TRUE)'
            ),
        )

        header = get_csv_header(changeset_csv_path)
        columns = tuple(f'"{c}"' for c in header.split(','))
        print(f'Populating changeset table ({len(columns)} columns)...')
        await session.execute(
            text(
                f'COPY "{Changeset.__tablename__}" ({", ".join(columns)}) '
                f"FROM PROGRAM 'zstd -d --stdout \"{changeset_csv_path.absolute()}\"' "
                f'(FORMAT CSV, FREEZE, HEADER TRUE)'
            ),
        )

        header = get_csv_header(element_csv_path)
        columns = tuple(f'"{c}"' for c in header.split(','))
        print(f'Populating element table ({len(columns)} columns)...')
        await session.execute(
            text(
                f'COPY "{Element.__tablename__}" ({", ".join(columns)}) '
                f"FROM PROGRAM 'zstd -d --stdout \"{element_csv_path.absolute()}\"' "
                f'(FORMAT CSV, FREEZE, HEADER TRUE)'
            ),
        )

        print('Reenabling triggers')
        await session.execute(text('SET session_replication_role TO default'))

    print(f'Recreating {len(index_create_sqls)} indexes...')
    async with create_task_group() as tg:

        async def task(sql: str) -> None:
            async with db() as session:
                await session.connection(execution_options={'isolation_level': 'AUTOCOMMIT'})
                await session.execute(text(sql))

        for create_sql in index_create_sqls:
            tg.start_soon(task, create_sql)

    print('Updating statistics')
    await db_update_stats()

    print('Fixing database consistency')
    await MigrationService.fix_sequence_counters()


if __name__ == '__main__':
    anyio.run(main)
    print('Done! Done! Done!')
