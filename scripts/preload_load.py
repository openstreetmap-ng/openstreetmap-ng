import csv
import gc
import pathlib

import anyio
from sqlalchemy import Index, select, text

from app.config import PRELOAD_DIR
from app.db import db_autocommit, db_update_stats
from app.models.db import *  # noqa: F403
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.user import User
from app.services.migration_service import MigrationService

user_csv_path = pathlib.Path(PRELOAD_DIR / 'user.csv')
changeset_csv_path = pathlib.Path(PRELOAD_DIR / 'changeset.csv')
element_csv_path = pathlib.Path(PRELOAD_DIR / 'element.csv')

# freeze all gc objects before starting for improved performance
gc.collect()
gc.freeze()
gc.disable()


async def main() -> None:
    for p in (user_csv_path, changeset_csv_path, element_csv_path):
        if not p.is_file():
            raise FileNotFoundError(f'File not found: {p}')

    async with db_autocommit() as session:
        if await session.scalar(select(Element).limit(1)):  # noqa: SIM102
            if input('Database is not empty. Continue? (y/N): ').lower() != 'y':
                print('Aborted')
                return

        # copy freeze requires truncate
        print('Truncating...')
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

        print('Populating user table...')
        with user_csv_path.open(newline='') as f:
            columns = next(iter(csv.reader(f)))
            columns = tuple(f'"{c}"' for c in columns)

        await session.execute(
            text(
                f'COPY "{User.__tablename__}" ({", ".join(columns)}) '
                f"FROM '{user_csv_path.absolute()}' "
                f'(FORMAT CSV, FREEZE, HEADER TRUE)'
            ),
        )

        print('Populating changeset table...')
        with changeset_csv_path.open(newline='') as f:
            columns = next(iter(csv.reader(f)))
            columns = tuple(f'"{c}"' for c in columns)

        await session.execute(
            text(
                f'COPY "{Changeset.__tablename__}" ({", ".join(columns)}) '
                f"FROM '{changeset_csv_path.absolute()}' "
                f'(FORMAT CSV, FREEZE, HEADER TRUE)'
            ),
        )

        print('Populating element table...')
        with element_csv_path.open(newline='') as f:
            columns = next(iter(csv.reader(f)))
            columns = tuple(f'"{c}"' for c in columns)

        await session.execute(
            text(
                f'COPY "{Element.__tablename__}" ({", ".join(columns)}) '
                f"FROM '{element_csv_path.absolute()}' "
                f'(FORMAT CSV, FREEZE, HEADER TRUE)'
            ),
        )

        print('Recreating indexes')
        for create_sql in index_create_sqls:
            await session.execute(text(create_sql))

        print('Reenabling triggers')
        await session.execute(text('SET session_replication_role TO default'))

    print('Updating statistics')
    await db_update_stats()

    print('Fixing database consistency')
    await MigrationService.fix_sequence_counters()


if __name__ == '__main__':
    anyio.run(main)
    print('Done! Done! Done!')
