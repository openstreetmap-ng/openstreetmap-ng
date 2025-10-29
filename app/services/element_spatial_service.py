import asyncio
import logging
from asyncio import Event, Semaphore, TaskGroup
from contextlib import asynccontextmanager, nullcontext
from math import ceil
from random import uniform
from time import monotonic
from typing import LiteralString

import cython
from sentry_sdk.api import start_transaction
from tqdm import tqdm

from app.db import db, db_lock, without_indexes
from app.lib.retry import retry
from app.lib.sentry import (
    SENTRY_ELEMENT_SPATIAL_MONITOR,
    SENTRY_ELEMENT_SPATIAL_MONITOR_SLUG,
)
from app.lib.testmethod import testmethod
from app.utils import calc_num_workers

_MAX_RELATION_NESTING_DEPTH = 12

_PROCESS_REQUEST_EVENT = Event()
_PROCESS_DONE_EVENT = Event()

_BATCH_QUERY_WAYS: LiteralString = """
WITH nodes AS (
    SELECT typed_id
    FROM element
    WHERE sequence_id BETWEEN %(start_seq)s AND %(end_seq)s
        AND typed_id <= 1152921504606846975
        AND latest
),
ways AS (
    SELECT w.typed_id, w.sequence_id
    FROM element w, (SELECT array_agg(typed_id) AS ids FROM nodes) n
    WHERE w.typed_id BETWEEN 1152921504606846976 AND 2305843009213693951
        AND w.latest
        AND w.members && n.ids
    UNION
    SELECT typed_id, sequence_id
    FROM element
    WHERE sequence_id BETWEEN %(start_seq)s AND %(end_seq)s
        AND typed_id BETWEEN 1152921504606846976 AND 2305843009213693951
        AND latest
),
ways_computed AS (
    SELECT
        w.typed_id,
        w.sequence_id,
        ST_RemoveRepeatedPoints(
            ST_QuantizeCoordinates(
                CASE
                    WHEN ST_IsClosed(line_geom) AND ST_NumPoints(line_geom) >= 4
                    THEN ST_MakePolygon(line_geom)
                    ELSE line_geom
                END,
                7
            )
        ) AS geom
    FROM element w
    INNER JOIN ways ON ways.sequence_id = w.sequence_id
    LEFT JOIN LATERAL (
        SELECT ST_MakeLine(node_point.point ORDER BY m.ord) AS line_geom
        FROM UNNEST(w.members) WITH ORDINALITY AS m(node_id, ord)
        LEFT JOIN LATERAL (
            SELECT point
            FROM element n
            WHERE n.typed_id = m.node_id
            ORDER BY n.sequence_id DESC
            LIMIT 1
        ) node_point ON true
        WHERE w.visible
    ) AS way_geom ON true
)
INSERT INTO element_spatial_staging (typed_id, sequence_id, updated_sequence_id, depth, geom)
SELECT typed_id, sequence_id, %(end_seq)s, 0, geom FROM ways_computed
"""

_BATCH_QUERY_RELATIONS: LiteralString = """
WITH
rels_batch AS (
    SELECT typed_id
    FROM element_spatial_pending_rels
    ORDER BY typed_id
    LIMIT %(batch_limit)s OFFSET %(batch_offset)s
),
rels AS (
    SELECT r.typed_id, r.sequence_id, r.members, r.visible, r.tags
    FROM element r
    INNER JOIN rels_batch ON rels_batch.typed_id = r.typed_id
    WHERE r.latest
),
rels_members AS (
    SELECT r.typed_id AS parent_id, m.member_id
    FROM rels r
    CROSS JOIN LATERAL UNNEST(r.members) AS m(member_id)
),
needed_ids AS (
    SELECT DISTINCT member_id AS typed_id
    FROM rels_members
    WHERE member_id >= 1152921504606846976
),
geom_lookup AS MATERIALIZED (
    SELECT typed_id, geom
    FROM (
        SELECT
            typed_id,
            geom,
            ROW_NUMBER() OVER (PARTITION BY typed_id ORDER BY updated_sequence_id DESC) AS rn
        FROM (
            SELECT
                s.typed_id,
                s.geom,
                s.updated_sequence_id
            FROM element_spatial_staging s
            INNER JOIN needed_ids n ON n.typed_id = s.typed_id
            WHERE s.depth < %(depth)s

            UNION ALL

            SELECT
                es.typed_id,
                es.geom,
                0 AS updated_sequence_id
            FROM element_spatial es
            INNER JOIN needed_ids n ON n.typed_id = es.typed_id
        )
    ) ranked
    WHERE rn = 1
),
rels_ready AS (
    SELECT r.*
    FROM rels r
    WHERE %(depth)s >= %(max_depth)s OR NOT EXISTS (
        SELECT 1
        FROM rels_members cm
        WHERE cm.parent_id = r.typed_id
          AND cm.member_id >= 2305843009213693952
          AND (
              EXISTS (
                  SELECT 1
                  FROM element_spatial_pending_rels pr
                  WHERE pr.typed_id = cm.member_id
              )
              OR NOT EXISTS (
                  SELECT 1
                  FROM geom_lookup gl
                  WHERE gl.typed_id = cm.member_id
              )
          )
    )
),
rels_computed AS (
    SELECT
        rr.typed_id,
        rr.sequence_id,
        rel_geom.geom
    FROM rels_ready rr
    LEFT JOIN LATERAL (
        WITH member_geoms AS (
            SELECT ST_Collect(geom_val) AS geom
            FROM (
                SELECT gl.geom AS geom_val
                FROM UNNEST(rr.members) AS m(child_rel_id)
                INNER JOIN geom_lookup gl ON gl.typed_id = m.child_rel_id
                WHERE m.child_rel_id >= 2305843009213693952
                    AND gl.geom IS NOT NULL

                UNION ALL

                SELECT COALESCE(gl.geom, node_point.point) AS geom_val
                FROM UNNEST(rr.members) AS m(member_id)
                LEFT JOIN geom_lookup gl ON gl.typed_id = m.member_id
                LEFT JOIN LATERAL (
                    SELECT point
                    FROM element n
                    WHERE n.typed_id = m.member_id
                    ORDER BY n.sequence_id DESC
                    LIMIT 1
                ) node_point ON m.member_id <= 1152921504606846975
                WHERE m.member_id <= 2305843009213693951
            )
        ),
        noded_geoms AS (
            SELECT ST_UnaryUnion(ST_Collect(
                ST_CollectionExtract(member_geoms.geom, 2),
                ST_Boundary(ST_CollectionExtract(member_geoms.geom, 3))
            )) AS geom
            FROM member_geoms
        ),
        polygon_geoms AS (
            SELECT ST_UnaryUnion(ST_Collect(
                ST_CollectionExtract(ST_Polygonize((SELECT geom FROM noded_geoms)), 3),
                ST_CollectionExtract((SELECT geom FROM member_geoms), 3)
            )) AS geom
        )
        SELECT ST_RemoveRepeatedPoints(
            ST_QuantizeCoordinates(
                ST_Collect(
                    CASE
                        WHEN ST_IsEmpty((SELECT geom FROM polygon_geoms)) AND ST_IsEmpty((SELECT geom FROM noded_geoms)) THEN NULL
                        ELSE ST_UnaryUnion(ST_Collect((SELECT geom FROM polygon_geoms), ST_LineMerge((SELECT geom FROM noded_geoms))))
                    END,
                    CASE
                        WHEN ST_IsEmpty(ST_CollectionExtract((SELECT geom FROM member_geoms), 1)) THEN NULL
                        ELSE ST_CollectionExtract((SELECT geom FROM member_geoms), 1)
                    END
                ),
                7
            )
        ) AS geom
        WHERE rr.visible
          AND rr.tags IS NOT NULL
    ) AS rel_geom ON true
)
INSERT INTO element_spatial_staging (typed_id, sequence_id, updated_sequence_id, depth, geom)
SELECT typed_id, sequence_id, %(end_seq)s, %(depth)s, geom FROM rels_computed
"""


class ElementSpatialService:
    @staticmethod
    @asynccontextmanager
    async def context():
        """Context manager for continuous element_spatial updates."""
        async with TaskGroup() as tg:
            task = tg.create_task(_process_task())
            yield
            task.cancel()

    @staticmethod
    @testmethod
    async def force_process():
        """
        Force the element_spatial processing loop to wake up early, and wait for it to finish.
        This method is only available during testing, and is limited to the current process.
        """
        logging.debug('Requesting element_spatial processing loop early wakeup')
        _PROCESS_REQUEST_EVENT.set()
        _PROCESS_DONE_EVENT.clear()
        await _PROCESS_DONE_EVENT.wait()


@retry(None)
async def _process_task() -> None:
    async def sleep(delay: float) -> None:
        if delay > 0:
            try:
                await asyncio.wait_for(_PROCESS_REQUEST_EVENT.wait(), timeout=delay)
            except TimeoutError:
                pass

    while True:
        async with db_lock(4729581063492817364) as acquired:
            if acquired:
                _PROCESS_REQUEST_EVENT.clear()

                ts = monotonic()
                with (
                    SENTRY_ELEMENT_SPATIAL_MONITOR,
                    start_transaction(
                        op='task', name=SENTRY_ELEMENT_SPATIAL_MONITOR_SLUG
                    ),
                ):
                    await _update()
                tt = monotonic() - ts

                if not _PROCESS_REQUEST_EVENT.is_set():
                    _PROCESS_DONE_EVENT.set()

                # on success, sleep ~5min
                await sleep(uniform(290, 310) - tt)
            else:
                # on failure, sleep ~1h
                await sleep(uniform(0.5 * 3600, 1.5 * 3600))


async def _update(
    *,
    parallelism: int | float = 0.5,
    parallelism_init: int | float = 1.0,
    ways_batch_size: int = 50_000,
    rels_batch_size: int = 1_000,
    _MAX_RELATION_NESTING_DEPTH: cython.Py_ssize_t = _MAX_RELATION_NESTING_DEPTH,
) -> None:
    """
    Update the element_spatial table with geometries and spatial indices for ways and relations.

    Uses incremental processing based on sequence_id watermark. Reactively detects affected
    parent elements when members change:
    - Ways updated when: the way itself changes OR any member node changes
    - Relations updated when: the relation itself changes OR any member node/way changes

    Multi-depth processing handles nested relations deterministically:
    - Depth 0: Process ways (no dependencies)
    - Depth 1+: Process relations iteratively by dependency depth until no more ready

    Two-stage approach enables deadlock-free parallel batch processing:
    1. Parallel batches write to element_spatial_staging across all depths (append-only, zero conflicts)
    2. Single atomic finalize operation merges all staged data → element_spatial at end

    Watermark tracks completion; crash restarts from last committed watermark.
    """
    async with (
        db() as conn,
        await conn.execute("""
            SELECT COALESCE(MAX(sequence_id), 0) FROM element
            UNION ALL
            SELECT COALESCE((SELECT sequence_id FROM element_spatial_watermark LIMIT 1), 0)
        """) as r,
    ):
        (max_sequence,), (last_sequence,) = await r.fetchall()

    num_items = max_sequence - last_sequence
    if not num_items:
        return

    # Rollback unfinished work
    async with db(True) as conn:
        await conn.execute('TRUNCATE element_spatial_staging')
        await conn.execute('TRUNCATE element_spatial_pending_rels')

    parallelism = calc_num_workers(parallelism if last_sequence else parallelism_init)
    logging.debug(
        'Updating element_spatial (batches=%d, parallelism=%d, sequence_id=%d..%d)',
        ceil(num_items / ways_batch_size),
        parallelism,
        last_sequence + 1,
        max_sequence,
    )

    # Process all depths (0=ways, 1+=relations)
    depth: cython.Py_ssize_t
    for depth in range(_MAX_RELATION_NESTING_DEPTH + 1):
        processed = await _process_depth(
            depth=depth,
            last_sequence=last_sequence,
            max_sequence=max_sequence,
            parallelism=parallelism,
            batch_size=ways_batch_size if not depth else rels_batch_size,
        )

        # Early exit for relations if nothing processed
        if depth and not processed:
            break

        # Seed pending relations for the next depth
        if depth < _MAX_RELATION_NESTING_DEPTH:
            await _seed_pending_relations(
                depth=depth, last_sequence=last_sequence, max_sequence=max_sequence
            )

    await _finalize_staging(max_sequence=max_sequence, last_sequence=last_sequence)


async def _process_depth(
    *,
    depth: int,
    last_sequence: int,
    max_sequence: int,
    parallelism: int,
    batch_size: int,
) -> bool:
    """Process a single depth of element_spatial updates."""
    # Determine what to process and how many items
    if depth:
        async with (
            # db(True) because element_spatial_pending_rels is UNLOGGED
            db(True) as conn,
            await conn.execute(
                'SELECT COUNT(*) FROM element_spatial_pending_rels'
            ) as r,
        ):
            (num_items,) = await r.fetchone()  # type: ignore
        if not num_items:
            logging.debug('Depth %d: No relations to process', depth)
            return False
        logging.debug('Depth %d: Processing %d relations', depth, num_items)
    else:
        num_items = max_sequence - last_sequence
        logging.debug('Depth 0: Processing %d changes', num_items)

    semaphore = Semaphore(parallelism)

    with (
        tqdm(desc=f'element_spatial_staging depth={depth}', total=num_items)
        if not last_sequence
        else nullcontext()
    ) as pbar:

        async def process_ways_batch(start_seq: int, end_seq: int):
            async with semaphore, db(True) as conn:
                await conn.execute(
                    _BATCH_QUERY_WAYS,
                    {
                        'start_seq': start_seq,
                        'end_seq': end_seq,
                        'last_seq': last_sequence,
                    },
                )
            if pbar is not None:
                pbar.update(end_seq - start_seq + 1)

        async def process_rels_batch(batch_offset: int):
            async with semaphore, db(True) as conn:
                await conn.execute(
                    _BATCH_QUERY_RELATIONS,
                    {
                        'depth': depth,
                        'max_depth': _MAX_RELATION_NESTING_DEPTH,
                        'last_seq': last_sequence,
                        'end_seq': max_sequence,
                        'batch_offset': batch_offset,
                        'batch_limit': batch_size,
                    },
                )
            if pbar is not None:
                pbar.update(min(batch_size, num_items - batch_offset))

        async with TaskGroup() as tg:
            if not depth:
                # Depth 0: Batch by sequence range
                for end_seq in range(max_sequence, last_sequence, -batch_size):
                    start_seq = max(end_seq - batch_size + 1, last_sequence + 1)
                    tg.create_task(process_ways_batch(start_seq, end_seq))
            else:
                # Depth 1+: Batch by offset into pending_rels
                for batch_offset in range(0, num_items, batch_size):
                    tg.create_task(process_rels_batch(batch_offset))

    if num_items >= 10_000:
        async with db(True) as conn:
            await conn.execute('ANALYZE element_spatial_staging')

    return True


async def _seed_pending_relations(
    *, depth: int, last_sequence: int, max_sequence: int
) -> None:
    """Populate pending relations table for the next depth."""
    logging.debug('Seeding pending relations after depth %d', depth)
    async with db(True) as conn:
        await conn.execute(
            """
            DELETE FROM element_spatial_pending_rels p
            USING element_spatial_staging s
            WHERE p.typed_id = s.typed_id
              AND s.depth = %(depth)s
            """,
            {'depth': depth},
        )
        await conn.execute(
            """
            WITH updated_members AS (
                SELECT typed_id
                FROM element_spatial_staging
                WHERE depth = %(depth)s

                UNION

                SELECT typed_id
                FROM element
                WHERE sequence_id BETWEEN %(start_seq)s AND %(end_seq)s
                  AND typed_id <= 1152921504606846975
                  AND latest
                  AND %(depth)s = 0
            ),
            candidate_rels AS (
                -- Relations directly updated in this range (computed only once at depth 0)
                SELECT r.typed_id
                FROM element r
                WHERE r.typed_id >= 2305843009213693952
                  AND r.latest
                  AND r.sequence_id BETWEEN %(start_seq)s AND %(end_seq)s
                  AND %(depth)s = 0

                UNION

                -- Relations whose members (nodes/ways/relations) were updated
                SELECT DISTINCT r.typed_id
                FROM element r
                JOIN LATERAL UNNEST(r.members) AS m(member_id) ON true
                JOIN updated_members um ON um.typed_id = m.member_id
                WHERE r.typed_id >= 2305843009213693952
                  AND r.latest
                  AND r.visible
                  AND r.tags IS NOT NULL
            )
            INSERT INTO element_spatial_pending_rels (typed_id)
            SELECT c.typed_id
            FROM candidate_rels c
            WHERE NOT EXISTS (
                SELECT 1
                FROM element_spatial_staging s
                WHERE s.typed_id = c.typed_id
            )
            ON CONFLICT DO NOTHING
            """,
            {
                'depth': depth,
                'start_seq': last_sequence + 1,
                'end_seq': max_sequence,
            },
        )
        await conn.execute('ANALYZE element_spatial_pending_rels')


async def _finalize_staging(*, max_sequence: int, last_sequence: int) -> None:
    """Merge staging table into element_spatial and advance watermark."""
    logging.debug('Finalizing element_spatial staging merge')

    async with (
        db(True) as conn,
        (
            without_indexes(conn, 'element_spatial')
            if not last_sequence
            else nullcontext()
        ),
    ):
        await conn.execute(
            """
            DELETE FROM element_spatial_staging s1
            WHERE EXISTS (
                SELECT 1
                FROM element_spatial_staging s2
                WHERE s2.typed_id = s1.typed_id
                  AND s2.updated_sequence_id > s1.updated_sequence_id
            )
            """
        )
        await conn.execute(
            """
            DELETE FROM element_spatial e
            USING element_spatial_staging s
            WHERE e.typed_id = s.typed_id
              AND s.geom IS NULL
            """
        )
        await conn.execute(
            """
            INSERT INTO element_spatial (typed_id, sequence_id, geom)
            SELECT typed_id, sequence_id, geom
            FROM element_spatial_staging
            WHERE geom IS NOT NULL
            ON CONFLICT (typed_id) DO UPDATE SET
                sequence_id = EXCLUDED.sequence_id,
                geom = EXCLUDED.geom
            """
        )
        await conn.execute(
            """
            INSERT INTO element_spatial_watermark (id, sequence_id)
            VALUES (1, %(seq)s)
            ON CONFLICT (id) DO UPDATE SET
                sequence_id = EXCLUDED.sequence_id
            """,
            {'seq': max_sequence},
        )

        await conn.execute('TRUNCATE element_spatial_staging')
        await conn.execute('TRUNCATE element_spatial_pending_rels')

    logging.debug('Finished updating element_spatial')
