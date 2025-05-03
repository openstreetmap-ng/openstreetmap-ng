import asyncio
import logging
from argparse import ArgumentParser
from asyncio import TaskGroup, to_thread
from pathlib import Path
from tempfile import mktemp

from app.config import REPLICATION_DIR, SQLITE_TMPDIR
from app.db import duckdb_connect, sqlite_connect
from app.models.element import (
    TYPED_ELEMENT_ID_RELATION_MAX,
    TYPED_ELEMENT_ID_RELATION_MIN,
)
from app.utils import calc_num_workers
from scripts.preload_convert import NOTES_PARQUET_PATH

_PARQUET_PATHS = [
    p.as_posix()
    for p in sorted(
        (
            *REPLICATION_DIR.glob('bundle_*.parquet'),
            *REPLICATION_DIR.glob('replica_*.parquet'),
        ),
        key=lambda p: int(p.stem.split('_', 1)[1]),
    )
]


def _process_changeset(header_only: bool) -> None:
    with duckdb_connect(progress=False) as conn:
        query = f"""
        SELECT
            changeset_id AS id,
            ARBITRARY(user_id) AS user_id,
            '' AS tags,
            MIN(created_at) AS created_at,
            MAX(created_at) AS updated_at,
            MAX(created_at) AS closed_at,
            COUNT(*) AS size,
            COUNT_IF(version = 1) AS num_create,
            COUNT_IF(version > 1 AND visible) AS num_modify,
            COUNT_IF(version > 1 AND NOT visible) AS num_delete
        FROM read_parquet({_PARQUET_PATHS!r})
        GROUP BY changeset_id
        """

        if header_only:
            query += ' LIMIT 0'

        conn.sql(query).write_csv('/dev/stdout')


def _process_element_worker(
    header_only: bool,
    sqlite_db: str,
    *,
    thread_id: int,
    parallelism: int,
):
    thread_paths = _PARQUET_PATHS[thread_id::parallelism]
    assert thread_paths
    sqlite_db += f'.{thread_id}'

    with sqlite_connect(sqlite_db, unsafe_faster=True) as conn:
        conn.execute("""
        CREATE TABLE typed_id_version
        (typed_id INTEGER, version INTEGER)
        """)

    if not header_only:
        with duckdb_connect(progress=False) as conn:
            conn.sql('LOAD sqlite')
            conn.sql(f'ATTACH {sqlite_db!r} AS sqlite (TYPE sqlite)')

            logging.info('[thr_%d] Populating sqlite.typed_id_version', thread_id)
            conn.sql(f"""
            INSERT INTO sqlite.typed_id_version
            SELECT typed_id, version
            FROM read_parquet({thread_paths!r})
            """)

    with sqlite_connect(sqlite_db, unsafe_faster=True) as conn:
        conn.execute("""
        CREATE TABLE mv
        (typed_id INTEGER, version INTEGER)
        """)

        logging.info('[thr_%d] Populating sqlite.mv', thread_id)
        conn.execute("""
        INSERT INTO mv
        SELECT typed_id, MAX(version) AS version
        FROM typed_id_version
        GROUP BY typed_id
        """)

        logging.info('[thr_%d] Cleaning sqlite database', thread_id)
        conn.execute('DROP TABLE typed_id_version')
        conn.execute('VACUUM')

        logging.info('[thr_%d] Building sqlite.mv index', thread_id)
        conn.execute('CREATE INDEX mv_idx ON mv (typed_id)')

        logging.info('[thr_%d] Optimizing sqlite database', thread_id)
        conn.execute('PRAGMA optimize')

    logging.info('[thr_%d] Database is ready', thread_id)
    return sqlite_db


async def _process_element(
    header_only: bool,
    *,
    parallelism: int | float = 1.0,
) -> None:
    parallelism = min(calc_num_workers(parallelism), len(_PARQUET_PATHS))

    with duckdb_connect(progress=False) as conn:
        logging.debug('Installing sqlite duckdb extension')
        conn.sql('INSTALL sqlite')

    sqlite_db_base = mktemp(  # noqa: S306
        prefix='osm-ng-sqlite-mv-',
        suffix='.db',
        dir=SQLITE_TMPDIR,
    )

    async with TaskGroup() as tg:
        tasks = [
            tg.create_task(
                to_thread(
                    _process_element_worker,
                    header_only=header_only,
                    sqlite_db=sqlite_db_base,
                    thread_id=thread_id,
                    parallelism=parallelism,
                )
            )
            for thread_id in range(parallelism)
        ]

    sqlite_dbs = [t.result() for t in tasks]
    logging.info('All worker threads completed')

    try:
        with duckdb_connect(progress=False) as conn:
            conn.sql('LOAD sqlite')
            for i, sqlite_db in enumerate(sqlite_dbs):
                alias = f'sqlite{i}'
                logging.debug('Attaching sqlite database %r as %r', sqlite_db, alias)
                conn.sql(f'ATTACH {sqlite_db!r} AS {alias} (TYPE sqlite)')

            # Utility for escaping text
            conn.execute("""
            CREATE MACRO quote(str) AS
            '"' || replace(replace(str, '\\', '\\\\'), '"', '\\"') || '"'
            """)

            # Convert map to Postgres-hstore format
            conn.execute("""
            CREATE MACRO map_to_hstore(m) AS
            array_to_string(
                list_transform(
                    map_entries(m),
                    entry -> quote(entry.key) || '=>' || quote(entry.value)
                ),
                ','
            )
            """)

            # Encode array in Postgres format
            conn.execute("""
            CREATE MACRO pg_array(arr) AS
            '{' || array_to_string(arr, ',') || '}'
            """)

            query = f"""
            SELECT
                sequence_id,
                changeset_id,
                e.typed_id,
                e.version,
                (
                    e.version =
                    COALESCE({', '.join(f'mv{i}.version' for i in range(parallelism))})
                ) AS latest,
                visible,
                IF(
                    tags IS NOT NULL,
                    map_to_hstore(tags),
                    NULL
                ) AS tags,
                hex(point) AS point,
                IF(
                    members IS NOT NULL,
                    pg_array(list_transform(members, x -> x.typed_id)),
                    NULL
                ) AS members,
                IF(
                    members IS NOT NULL
                    AND e.typed_id BETWEEN
                    {TYPED_ELEMENT_ID_RELATION_MIN} AND {TYPED_ELEMENT_ID_RELATION_MAX},
                    pg_array(list_transform(members, x -> quote(x.role))),
                    NULL
                ) AS members_roles,
                created_at
            FROM read_parquet({_PARQUET_PATHS!r}) e
            {
                '\n'.join(
                    f'LEFT JOIN sqlite{i}.mv mv{i} ON e.typed_id = mv{i}.typed_id'
                    for i in range(parallelism)
                )
            }
            """

            if header_only:
                query += ' LIMIT 0'

            conn.sql(query).write_csv('/dev/stdout')

    finally:
        for sqlite_db in sqlite_dbs:
            logging.debug('Removing sqlite database %r', sqlite_db)
            Path(sqlite_db).unlink()


def _process_user(header_only: bool) -> None:
    with duckdb_connect(progress=False) as conn:
        sources = [
            f"""
            SELECT DISTINCT ON (user_id)
                user_id,
                display_name
            FROM read_parquet({_PARQUET_PATHS!r})
            WHERE user_id IS NOT NULL
            """
        ]

        if NOTES_PARQUET_PATH.is_file():
            logging.info('User data WILL include notes data')
            sources.append(f"""
            SELECT DISTINCT ON (user_id)
                user_id,
                display_name
            FROM (
                SELECT UNNEST(comments, max_depth := 2)
                FROM read_parquet({NOTES_PARQUET_PATH.as_posix()!r})
            )
            WHERE user_id IS NOT NULL
            """)
        else:
            logging.warning(
                'User data WILL NOT include notes data: source file not found'
            )

        query = f"""
        SELECT DISTINCT ON (user_id)
            user_id AS id,
            (user_id || '@localhost.invalid') AS email,
            TRUE as email_verified,
            IF(
                COUNT(*) OVER (PARTITION BY display_name) > 1,
                display_name || '_' || user_id,
                display_name
            ) AS display_name,
            '' AS password_pb,
            'en' AS language,
            TRUE AS activity_tracking,
            TRUE AS crash_reporting,
            '127.0.0.1' AS created_ip
        FROM ({' UNION ALL '.join(sources)})
        """

        if header_only:
            query += ' LIMIT 0'

        conn.sql(query).write_csv('/dev/stdout')


async def main() -> None:
    choices = ['changeset', 'element', 'user']
    parser = ArgumentParser()
    parser.add_argument('--header-only', action='store_true')
    parser.add_argument('mode', choices=choices)
    args = parser.parse_args()

    logging.info('Found %d source parquet files', len(_PARQUET_PATHS))

    match args.mode:
        case 'changeset':
            _process_changeset(args.header_only)
        case 'element':
            await _process_element(args.header_only)
        case 'user':
            _process_user(args.header_only)
        case _:
            raise ValueError(f'Invalid mode: {args.mode}')


if __name__ == '__main__':
    asyncio.run(main())
