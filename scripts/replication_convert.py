import logging
from argparse import ArgumentParser

from app.config import REPLICATION_DIR
from app.db import duckdb_connect
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


def _process_changeset() -> None:
    with duckdb_connect(progress=False) as conn:
        conn.sql(f"""
        SELECT
            changeset_id AS id,
            ANY_VALUE(user_id) AS user_id,
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
        """).write_csv('/dev/stdout')


def _process_element() -> None:
    with duckdb_connect(progress=False) as conn:
        # Compute typed_id from type and id.
        # Source implementation: app.models.element.typed_element_id
        conn.execute("""
        CREATE MACRO typed_element_id(type, id) AS
        CASE
            WHEN type = 'node' THEN id
            WHEN type = 'way' THEN (id | (1::bigint << 60))
            WHEN type = 'relation' THEN (id | (2::bigint << 60))
            ELSE NULL
        END
        """)

        # Utilities for escaping text
        conn.execute("""
        CREATE MACRO quote(str) AS
        '"' || replace(replace(str, '\\', '\\\\'), '"', '\\"') || '"'
        """)
        conn.execute("""
        CREATE MACRO jsonpointer_escape(key) AS
        '/' || replace(replace(key, '~', '~0'), '/', '~1')
        """)

        # Convert JSON dict to hstore
        conn.execute("""
        CREATE MACRO json_to_hstore(json) AS
        array_to_string(
            list_transform(
                json_keys(json),
                k -> quote(k) || '=>' || quote(json_extract_string(json, jsonpointer_escape(k)))
            ),
            ','
        )
        """)

        # Encode array in Postgres-compatible format
        conn.execute("""
        CREATE MACRO pg_array(arr) AS
        '{' || array_to_string(arr, ',') || '}'
        """)

        conn.sql(f"""
        SELECT
            sequence_id,
            changeset_id,
            typed_element_id(type, id) AS typed_id,
            version,
            visible,
            CASE
                WHEN tags != '{{}}' THEN
                    json_to_hstore(tags)
                ELSE NULL
            END AS tags,
            point,
            CASE
                WHEN len(members) > 0 THEN
                    pg_array(list_transform(members, x -> typed_element_id(x.type, x.id)))
                ELSE NULL
            END AS members,
            CASE
                WHEN len(members) > 0 AND type = 'relation' THEN
                    pg_array(list_transform(members, x -> quote(x.role)))
                ELSE NULL
            END AS members_roles,
            created_at
        FROM read_parquet({_PARQUET_PATHS!r})
        """).write_csv('/dev/stdout')


def _process_user() -> None:
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
            logging.warning('User data WILL NOT include notes data: source file not found')

        conn.sql(f"""
        SELECT DISTINCT ON (user_id)
            user_id AS id,
            (user_id || '@localhost.invalid') AS email,
            TRUE as email_verified,
            CASE
                WHEN COUNT(*) OVER (PARTITION BY display_name) > 1
                THEN display_name || '_' || user_id
                ELSE display_name
            END AS display_name,
            '' AS password_pb,
            'en' AS language,
            TRUE AS activity_tracking,
            TRUE AS crash_reporting,
            '127.0.0.1' AS created_ip
        FROM (
            {' UNION ALL '.join(sources)}
        )
        """).write_csv('/dev/stdout')


def main() -> None:
    choices = ['changeset', 'element', 'user']
    parser = ArgumentParser()
    parser.add_argument('mode', choices=choices)
    args = parser.parse_args()

    logging.info('Found %d source parquet files', len(_PARQUET_PATHS))

    match args.mode:
        case 'changeset':
            _process_changeset()
        case 'element':
            _process_element()
        case 'user':
            _process_user()
        case _:
            raise ValueError(f'Invalid mode: {args.mode}')


if __name__ == '__main__':
    main()
