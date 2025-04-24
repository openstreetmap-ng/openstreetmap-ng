import logging
from argparse import ArgumentParser

from app.config import REPLICATION_DIR
from app.db import duckdb_connect
from app.models.element import (
    TYPED_ELEMENT_ID_RELATION_MAX,
    TYPED_ELEMENT_ID_RELATION_MIN,
)
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


def _process_element(header_only: bool) -> None:
    with duckdb_connect(progress=False) as conn:
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
            typed_id,
            version,
            FALSE AS latest,
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
                AND typed_id BETWEEN {TYPED_ELEMENT_ID_RELATION_MIN} AND {TYPED_ELEMENT_ID_RELATION_MAX},
                pg_array(list_transform(members, x -> quote(x.role))),
                NULL
            ) AS members_roles,
            created_at
        FROM read_parquet({_PARQUET_PATHS!r})
        """

        if header_only:
            query += ' LIMIT 0'

        conn.sql(query).write_csv('/dev/stdout')


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


def main() -> None:
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
            _process_element(args.header_only)
        case 'user':
            _process_user(args.header_only)
        case _:
            raise ValueError(f'Invalid mode: {args.mode}')


if __name__ == '__main__':
    main()
