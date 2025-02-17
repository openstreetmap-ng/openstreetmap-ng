import asyncio
import shutil

import duckdb

from app.config import PRELOAD_DIR, REPLICATION_DIR
from app.db import duckdb_connect

_PARQET_PATHS = [
    p.as_posix()
    for p in sorted(
        (
            *REPLICATION_DIR.glob('bundle_*.parquet'),
            *REPLICATION_DIR.glob('replica_*.parquet'),
        ),
        key=lambda p: int(p.stem.split('_', 1)[1]),
    )
]


def _write_output(
    conn: duckdb.DuckDBPyConnection, parquets: duckdb.DuckDBPyRelation, table: str, select_sql: str, header: str
) -> None:
    output = PRELOAD_DIR.joinpath(table)
    shutil.rmtree(output, ignore_errors=True)
    conn.sql(f'COPY ({select_sql}) TO {output.as_posix()!r} (PER_THREAD_OUTPUT TRUE, COMPRESSION ZSTD, HEADER FALSE)')
    output.joinpath('header.csv').write_text(header)


def _write_changeset() -> None:
    with duckdb_connect() as conn:
        parquets = conn.read_parquet(_PARQET_PATHS)  # type: ignore
        changeset_sql = """
        SELECT
            changeset_id AS id,
            ANY_VALUE(user_id) AS user_id,
            MAX(created_at) AS closed_at,
            COUNT(*) AS size,
            '{}' AS tags
        FROM parquets
        GROUP BY changeset_id
        """
        _write_output(conn, parquets, 'changeset', changeset_sql, 'id,user_id,closed_at,size,tags')


def _write_element() -> None:
    with duckdb_connect() as conn:
        parquets = conn.read_parquet(_PARQET_PATHS)  # type: ignore
        element_sql = """
        SELECT
            sequence_id,
            changeset_id,
            type,
            id,
            version,
            visible,
            tags,
            point,
            created_at,
            LEAD(sequence_id) OVER w AS next_sequence_id
        FROM parquets
        WINDOW w AS (PARTITION BY type, id ORDER BY sequence_id)
        """
        _write_output(
            conn,
            parquets,
            'element',
            element_sql,
            'sequence_id,changeset_id,type,id,version,visible,tags,point,created_at,next_sequence_id',
        )
        conn.sql('DROP TABLE sequence')


def _write_element_member() -> None:
    with duckdb_connect() as conn:
        parquets = conn.read_parquet(_PARQET_PATHS)  # type: ignore
        element_member_sql = """
        SELECT
            sequence_id,
            UNNEST(members, max_depth := 2)
        FROM parquets
        """
        _write_output(conn, parquets, 'element_member', element_member_sql, 'sequence_id,order,type,id,role')


def _write_user() -> None:
    with duckdb_connect() as conn:
        parquets = conn.read_parquet(_PARQET_PATHS)  # type: ignore
        user_sql = """
        SELECT DISTINCT ON (user_id)
            user_id AS id,
            display_name,
            (user_id || '@localhost.invalid') AS email,
            '' AS password_pb,
            '127.0.0.1' AS created_ip,
            'active' AS status,
            'en' AS language,
            TRUE AS activity_tracking,
            TRUE AS crash_reporting
        FROM parquets
        WHERE user_id IS NOT NULL
        """
        _write_output(
            conn,
            parquets,
            'user',
            user_sql,
            'id,display_name,email,password_pb,created_ip,status,language,activity_tracking,crash_reporting',
        )


async def main() -> None:
    PRELOAD_DIR.mkdir(exist_ok=True, parents=True)
    print('Writing changeset')
    _write_changeset()
    print('Writing element')
    _write_element()
    print('Writing element member')
    _write_element_member()
    print('Writing user')
    _write_user()


if __name__ == '__main__':
    asyncio.run(main())
    print('Done! Done! Done!')
