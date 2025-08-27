import logging
from argparse import ArgumentParser

from app.config import REPLICATION_CONVERT_ELEMENT_BATCH_SIZE, REPLICATION_DIR
from app.db import duckdb_connect
from app.models.element import (
    TYPED_ELEMENT_ID_NODE_MAX,
    TYPED_ELEMENT_ID_RELATION_MIN,
    TYPED_ELEMENT_ID_WAY_MAX,
    TYPED_ELEMENT_ID_WAY_MIN,
)
from app.services.migration_service import _get_element_typed_id_batches
from scripts.preload_convert import CHANGESETS_PARQUET_PATH, NOTES_PARQUET_PATH

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

        query = f"""
        WITH planet_agg AS (
            SELECT
                changeset_id AS id,
                ARBITRARY(user_id) AS user_id,
                MIN(created_at) AS created_at,
                MAX(created_at) AS updated_at,
                MAX(created_at) AS closed_at,
                COUNT(*) AS size,
                COUNT_IF(version = 1) AS num_create,
                COUNT_IF(version > 1 AND visible) AS num_modify,
                COUNT_IF(version > 1 AND NOT visible) AS num_delete
            FROM read_parquet({_PARQUET_PATHS!r})
            GROUP BY changeset_id
            ORDER BY changeset_id
        )
        SELECT
            id,
            user_id,
            IF(
                tags IS NOT NULL,
                map_to_hstore(tags),
                ''
            ) AS tags,
            created_at,
            updated_at,
            closed_at,
            size,
            num_create,
            num_modify,
            num_delete,
            hex(bounds) AS union_bounds
        FROM planet_agg
        LEFT JOIN read_parquet({CHANGESETS_PARQUET_PATH.as_posix()!r}) USING (id)
        """

        if header_only:
            query += ' LIMIT 0'

        conn.sql(query).write_csv('/dev/stdout')


def _process_changeset_bounds(header_only: bool) -> None:
    with duckdb_connect(progress=False) as conn:
        query = f"""
        SELECT
            id AS changeset_id,
            hex(bounds) AS bounds
        FROM read_parquet({CHANGESETS_PARQUET_PATH.as_posix()!r})
        WHERE EXISTS (
            SELECT 1
            FROM read_parquet({_PARQUET_PATHS!r})
            WHERE changeset_id = id
        )
        """

        if header_only:
            query += ' LIMIT 0'

        conn.sql(query).write_csv('/dev/stdout')


def _process_element(
    header_only: bool, *, batch_size=REPLICATION_CONVERT_ELEMENT_BATCH_SIZE
) -> None:
    with duckdb_connect(progress=False) as conn:
        r: tuple[int, ...] = (
            conn.execute(f"""
            SELECT
                -- Nodes
                MIN(typed_id) FILTER (typed_id <= {TYPED_ELEMENT_ID_NODE_MAX}) AS node_min,
                MAX(typed_id) FILTER (typed_id <= {TYPED_ELEMENT_ID_NODE_MAX}) AS node_max,
                -- Ways
                MIN(typed_id) FILTER (typed_id BETWEEN {TYPED_ELEMENT_ID_WAY_MIN} AND {TYPED_ELEMENT_ID_WAY_MAX}) AS way_min,
                MAX(typed_id) FILTER (typed_id BETWEEN {TYPED_ELEMENT_ID_WAY_MIN} AND {TYPED_ELEMENT_ID_WAY_MAX}) AS way_max,
                -- Relations
                MIN(typed_id) FILTER (typed_id >= {TYPED_ELEMENT_ID_RELATION_MIN}) AS rel_min,
                MAX(typed_id) FILTER (typed_id >= {TYPED_ELEMENT_ID_RELATION_MIN}) AS rel_max
            FROM read_parquet({_PARQUET_PATHS!r})
            """).fetchone()  # type: ignore
            if not header_only
            else (0, 0)
        )

        ranges = [(r[i], r[i + 1]) for i in range(0, len(r), 2)]
        batches = _get_element_typed_id_batches(ranges, batch_size)
        logging.info('Processing in %d batches', len(batches))

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

        query = ' UNION ALL '.join([
            f"""(
            WITH max_versions AS (
                SELECT typed_id, MAX(version) AS version
                FROM read_parquet({_PARQUET_PATHS!r})
                WHERE typed_id BETWEEN {start_id} AND {end_id}
                GROUP BY typed_id
            )
            SELECT
                sequence_id,
                changeset_id,
                e.typed_id,
                e.version,
                (e.version = mv.version) AS latest,
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
                    AND e.typed_id >= {TYPED_ELEMENT_ID_RELATION_MIN},
                    pg_array(list_transform(members, x -> quote(x.role))),
                    NULL
                ) AS members_roles,
                created_at
            FROM read_parquet({_PARQUET_PATHS!r}) e
            JOIN max_versions mv ON e.typed_id = mv.typed_id
            WHERE e.typed_id BETWEEN {start_id} AND {end_id}
            {'LIMIT 0' if header_only else ''}
            )"""
            for start_id, end_id in batches
        ])

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
            TRUE AS crash_reporting
        FROM ({' UNION ALL '.join(sources)})
        """

        if header_only:
            query += ' LIMIT 0'

        conn.sql(query).write_csv('/dev/stdout')


def main() -> None:
    choices = ['changeset', 'changeset_bounds', 'element', 'user']
    parser = ArgumentParser()
    parser.add_argument('--header-only', action='store_true')
    parser.add_argument('mode', choices=choices)
    args = parser.parse_args()

    logging.info('Found %d source parquet files', len(_PARQUET_PATHS))

    match args.mode:
        case 'changeset':
            _process_changeset(args.header_only)
        case 'changeset_bounds':
            _process_changeset_bounds(args.header_only)
        case 'element':
            _process_element(args.header_only)
        case 'user':
            _process_user(args.header_only)
        case _:
            raise ValueError(f'Invalid mode: {args.mode}')


if __name__ == '__main__':
    main()
