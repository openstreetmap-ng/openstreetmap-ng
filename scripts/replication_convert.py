import asyncio
import shutil

import duckdb

from app.config import PRELOAD_DIR, REPLICATION_DIR
from app.db import duckdb_connect


def _write_output(
    conn: duckdb.DuckDBPyConnection, parquets: duckdb.DuckDBPyRelation, table: str, select_sql: str, header: str
) -> None:
    output = PRELOAD_DIR.joinpath(table)
    shutil.rmtree(output, ignore_errors=True)
    conn.sql(f'COPY ({select_sql}) TO {output.as_posix()!r} (PER_THREAD_OUTPUT TRUE, COMPRESSION ZSTD, HEADER FALSE)')
    output.joinpath('header.csv').write_text(header)


def _write_changeset(conn: duckdb.DuckDBPyConnection, parquets: duckdb.DuckDBPyRelation) -> None:
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


def _write_element(conn: duckdb.DuckDBPyConnection, parquets: duckdb.DuckDBPyRelation) -> None:
    conn.sql("""
    CREATE TEMP TABLE element_next AS
    SELECT
        sequence_id,
        type,
        id
    FROM parquets
    """)
    conn.sql('CREATE INDEX type_id_sequence_id_idx ON element_next (type, id, sequence_id)')
    element_sql = """
    SELECT
        p.sequence_id,
        p.changeset_id,
        p.type,
        p.id,
        p.version,
        p.visible,
        p.tags,
        p.point,
        p.created_at,
        next.sequence_id
    FROM parquets p
    ASOF LEFT JOIN element_next next
     ON next.type = p.type
    AND next.id = p.id
    AND next.sequence_id > p.sequence_id
    """
    _write_output(
        conn,
        parquets,
        'element',
        element_sql,
        'sequence_id,changeset_id,type,id,version,visible,tags,point,created_at,next_sequence_id',
    )
    conn.sql('DROP TABLE element_next')


def _write_element_member(conn: duckdb.DuckDBPyConnection, parquets: duckdb.DuckDBPyRelation) -> None:
    element_member_sql = """
    SELECT
        sequence_id,
        UNNEST(members, max_depth := 2)
    FROM parquets
    """
    _write_output(conn, parquets, 'element_member', element_member_sql, 'sequence_id,order,type,id,role')


def _write_user(conn: duckdb.DuckDBPyConnection, parquets: duckdb.DuckDBPyRelation) -> None:
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
    with duckdb_connect() as conn:
        print('Reading parquet files')
        parquet_paths = [
            p.as_posix()
            for p in sorted(
                (
                    *REPLICATION_DIR.glob('bundle_*.parquet'),
                    *REPLICATION_DIR.glob('replica_*.parquet'),
                ),
                key=lambda p: int(p.stem.split('_', 1)[1]),
            )
        ]
        parquets = conn.read_parquet(parquet_paths)  # type: ignore

        print('Writing changeset')
        _write_changeset(conn, parquets)
        print('Writing element')
        _write_element(conn, parquets)
        print('Writing element member')
        _write_element_member(conn, parquets)
        print('Writing user')
        _write_user(conn, parquets)


if __name__ == '__main__':
    asyncio.run(main())
    print('Done! Done! Done!')
