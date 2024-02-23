import csv
import pathlib

import anyio
from sqlalchemy import Index, select, text

from app.config import PRELOAD_DIR
from app.db import db_autocommit
from app.models.db import *  # noqa: F403
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.user import User


async def main():
    input_user_path = pathlib.Path(PRELOAD_DIR / 'user.csv')
    if not input_user_path.is_file():
        raise FileNotFoundError(f'File not found: {input_user_path}')

    input_changeset_path = pathlib.Path(PRELOAD_DIR / 'changeset.csv')
    if not input_changeset_path.is_file():
        raise FileNotFoundError(f'File not found: {input_changeset_path}')

    input_element_path = pathlib.Path(PRELOAD_DIR / 'element.csv')
    if not input_element_path.is_file():
        raise FileNotFoundError(f'File not found: {input_element_path}')

    async with db_autocommit() as session:
        if await session.scalar(select(Element).limit(1)):
            if input('Database is not empty. Truncate? (y/N): ').lower() == 'y':
                print('Truncating...')
            else:
                print('Aborted')
                return

        print('Disabling triggers')
        await session.execute(text('SET session_replication_role TO replica'))

        # discover indexes on the element table
        indexes = [arg for arg in Element.__table_args__ if isinstance(arg, Index)]

        for index in indexes:
            print(f'Dropping index {index.name!r}')
            index.drop(session.bind)

        # copy requires truncate
        await session.execute(
            text(f'TRUNCATE "{Element.__tablename__}", "{Changeset.__tablename__}", "{User.__tablename__}" CASCADE')
        )

        print('Populating user table...')
        with input_user_path.open(newline='') as f:
            columns = next(iter(csv.reader(f)))
            columns = tuple(f'"{c}"' for c in columns)

        await session.execute(
            text(
                f'COPY "{User.__tablename__}" ({", ".join(columns)}) '
                f"FROM '{input_user_path.absolute()}' "
                f'(FORMAT CSV, FREEZE, HEADER TRUE)'
            ),
        )

        print('Populating changeset table...')
        with input_changeset_path.open(newline='') as f:
            columns = next(iter(csv.reader(f)))
            columns = tuple(f'"{c}"' for c in columns)

        await session.execute(
            text(
                f'COPY "{Changeset.__tablename__}" ({", ".join(columns)}) '
                f"FROM '{input_changeset_path.absolute()}' "
                f'(FORMAT CSV, FREEZE, HEADER TRUE)'
            ),
        )

        print('Populating element table...')
        with input_element_path.open(newline='') as f:
            columns = next(iter(csv.reader(f)))
            columns = tuple(f'"{c}"' for c in columns)

        await session.execute(
            text(
                f'COPY "{Element.__tablename__}" ({", ".join(columns)}) '
                f"FROM '{input_element_path.absolute()}' "
                f'(FORMAT CSV, FREEZE, HEADER TRUE)'
            ),
        )

        for index in indexes:
            print(f'Recreating index {index.name!r}...')
            index.create(session.bind)

        print('Re-enabling triggers')
        await session.execute(text('SET session_replication_role TO default'))

        print('Done! Done! Done!')


if __name__ == '__main__':
    anyio.run(main)
