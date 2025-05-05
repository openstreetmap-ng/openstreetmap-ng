import logging
from argparse import ArgumentParser

import polars as pl

from app.config import REPLICATION_DIR
from app.db import duckdb_connect
from app.models.element import (
    TYPED_ELEMENT_ID_NODE_MAX,
    TYPED_ELEMENT_ID_NODE_MIN,
    TYPED_ELEMENT_ID_RELATION_MAX,
    TYPED_ELEMENT_ID_RELATION_MIN,
    TYPED_ELEMENT_ID_WAY_MAX,
    TYPED_ELEMENT_ID_WAY_MIN,
)
from app.services.migration_service import (
    _get_element_typed_id_batches,  # noqa: PLC2701
)
from scripts.preload_convert import (
    NOTES_PARQUET_PATH,
    pl_map_to_hstore,
    pl_pg_array,
    pl_quote,
)

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
    query = (
        pl.scan_parquet(_PARQUET_PATHS, low_memory=True, cache=False)
        .group_by('changeset_id')
        .agg(
            user_id=pl.first('user_id'),
            tags=pl.lit(''),
            created_at=pl.min('created_at'),
            updated_at=pl.max('created_at'),
            closed_at=pl.max('created_at'),
            size=pl.len(),
            num_create=pl.col('version').filter(pl.col('version') == 1).len(),
            num_modify=(
                pl.col('version')
                .filter((pl.col('version') > 1) & pl.col('visible'))
                .len()
            ),
            num_delete=(
                pl.col('version')
                .filter((pl.col('version') > 1) & ~pl.col('visible'))
                .len()
            ),
        )
        .rename({'changeset_id': 'id'})
        .select(
            'id',
            'user_id',
            'tags',
            'created_at',
            'updated_at',
            'closed_at',
            'size',
            'num_create',
            'num_modify',
            'num_delete',
        )
    )

    # pprint([
    #     {'node': d['node'], 'total': d['end'] - d['start']}
    #     for d in query.limit(10000).profile()[1].to_dicts()
    # ])
    # return

    # pprint(query.limit(10).collect().to_dicts())
    # return

    if header_only:
        schema = query.collect_schema()
        print(','.join(schema.names()))
        return

    query.sink_csv('/dev/stdout', include_header=False, maintain_order=False)


def _process_element(header_only: bool, *, batch_size=500_000_000) -> None:
    input = pl.scan_parquet(_PARQUET_PATHS, low_memory=True, cache=False)

    def typed_id_range(typed_id_min: int, typed_id_max: int, /) -> tuple[int, int]:
        return typed_id_min, (
            input.select('typed_id')
            .filter(pl.col('typed_id') <= typed_id_max)
            .max()
            .collect()
            .to_dicts()[0]['typed_id']
        )

    ranges = (
        [
            typed_id_range(TYPED_ELEMENT_ID_NODE_MIN, TYPED_ELEMENT_ID_NODE_MAX),
            typed_id_range(TYPED_ELEMENT_ID_WAY_MIN, TYPED_ELEMENT_ID_WAY_MAX),
            typed_id_range(
                TYPED_ELEMENT_ID_RELATION_MIN, TYPED_ELEMENT_ID_RELATION_MAX
            ),
        ]
        if not header_only
        else [(0, 0)]
    )
    batches = _get_element_typed_id_batches(ranges, batch_size)
    logging.info('Processing in %d batches', len(batches))

    for i, (start_id, end_id) in enumerate(batches, 1):
        logging.debug(
            'Processing batch %d of %d: %d - %d', i, len(batches), start_id, end_id
        )
        input_batch = input.filter(pl.col('typed_id').is_between(start_id, end_id))

        query = (
            input_batch.join(
                (
                    input_batch.select('typed_id', 'version')
                    .group_by('typed_id')
                    .agg(max_version=pl.max('version'))
                ),
                on='typed_id',
                how='left',  # fastest
            )
            .with_columns(
                latest=pl.col('version') == pl.col('max_version'),
                tags=(
                    pl.when(pl.col('tags').is_not_null())
                    .then(pl_map_to_hstore(pl.col('tags')))
                    .otherwise(None)
                ),
                point=(
                    pl.when(pl.col('point').is_not_null())
                    .then(pl.col('point').bin.encode('hex'))
                    .otherwise(None)
                ),
                members=(
                    pl.when(pl.col('members').is_not_null())
                    .then(
                        pl_pg_array(
                            pl.col('members').list.eval(
                                pl.element().struct.field('typed_id').cast(pl.String)
                            )
                        )
                    )
                    .otherwise(None)
                ),
                members_roles=(
                    pl.when(
                        pl.col('members').is_not_null()
                        & pl.col('typed_id').is_between(
                            TYPED_ELEMENT_ID_RELATION_MIN, TYPED_ELEMENT_ID_RELATION_MAX
                        )
                    )
                    .then(
                        pl_pg_array(
                            pl.col('members').list.eval(
                                pl_quote(
                                    pl.element().struct.field('role').cast(pl.String)
                                )
                            )
                        )
                    )
                    .otherwise(None)
                ),
            )
            .select(
                'sequence_id',
                'changeset_id',
                'typed_id',
                'version',
                'latest',
                'visible',
                'tags',
                'point',
                'members',
                'members_roles',
                'created_at',
            )
        )

        if header_only:
            schema = query.collect_schema()
            print(','.join(schema.names()))
            return

        query.sink_csv('/dev/stdout', include_header=False, maintain_order=False)


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
