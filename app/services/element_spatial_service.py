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

from app.db import db, db_lock, without_indexes
from app.lib.progress import progress
from app.lib.retry import retry
from app.lib.sentry import (
    SENTRY_ELEMENT_SPATIAL_MONITOR,
    SENTRY_ELEMENT_SPATIAL_MONITOR_SLUG,
)
from app.lib.testmethod import testmethod
from app.models.types import SequenceId
from app.utils import calc_num_workers

_MAX_RELATION_NESTING_DEPTH = 15

_PROCESS_REQUEST_EVENT = Event()
_PROCESS_DONE_EVENT = Event()

_BATCH_QUERY_WAYS: LiteralString = """
/*+ NoSeqScan(wc) */
WITH nodes AS (
    SELECT array_agg(typed_id) AS ids
    FROM element
    WHERE sequence_id BETWEEN %(start_seq)s AND %(end_seq)s
      AND typed_id <= 1152921504606846975
      AND latest
),
ways AS (
    SELECT w.typed_id, w.sequence_id
    FROM element w
    CROSS JOIN nodes n
    WHERE w.typed_id BETWEEN 1152921504606846976 AND 2305843009213693951
      AND w.latest
      AND (
        w.sequence_id BETWEEN %(start_seq)s AND %(end_seq)s
        OR w.members && n.ids
      )
),
ways_computed AS (
    SELECT
        wc.typed_id,
        wc.sequence_id,
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
    FROM element wc
    INNER JOIN ways ON ways.sequence_id = wc.sequence_id
    LEFT JOIN LATERAL (
        SELECT ST_MakeLine(node_point.point ORDER BY m.ord) AS line_geom
        FROM UNNEST(wc.members) WITH ORDINALITY AS m(node_id, ord)
        LEFT JOIN LATERAL (
            SELECT point
            FROM element n
            WHERE n.typed_id = m.node_id
            ORDER BY n.sequence_id DESC
            LIMIT 1
        ) node_point ON true
        WHERE wc.visible
          AND wc.members IS NOT NULL
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
    OFFSET %(batch_offset)s
    LIMIT %(batch_limit)s
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
    -- Priority 1: Staging (current cycle, most recent)
    (
        SELECT DISTINCT ON (s.typed_id) s.typed_id, s.geom
        FROM element_spatial_staging s
        INNER JOIN needed_ids n ON n.typed_id = s.typed_id
        WHERE s.depth < %(depth)s
        ORDER BY s.typed_id, s.updated_sequence_id DESC
    )

    UNION ALL

    -- Priority 2: Production table (previous cycles, fallback only)
    (
        SELECT es.typed_id, es.geom
        FROM element_spatial es
        INNER JOIN needed_ids n ON n.typed_id = es.typed_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM element_spatial_staging s
            WHERE s.typed_id = es.typed_id
              AND s.depth < %(depth)s
        )
    )
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
        -- TODO: Remove `NOT MATERIALIZED` after BUG #19106 is fixed
        WITH member_geoms AS NOT MATERIALIZED (
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
        noded_geoms AS NOT MATERIALIZED (
            SELECT ST_UnaryUnion(ST_Collect(
                ST_CollectionExtract(member_geoms.geom, 2),
                ST_Boundary(ST_CollectionExtract(member_geoms.geom, 3))
            )) AS geom
            FROM member_geoms
        ),
        polygon_geoms AS NOT MATERIALIZED (
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
          AND rr.members IS NOT NULL
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
    parallelism_init: int | float = 1.5,
    ways_batch_size: int = 10_000,
    rels_batch_size: int = 1_000,
    _MAX_RELATION_NESTING_DEPTH: cython.size_t = _MAX_RELATION_NESTING_DEPTH,
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
        await conn.execute(
            """
            SELECT
            (   SELECT COALESCE(MAX(sequence_id), 0) FROM element),
            (   SELECT COALESCE((SELECT sequence_id FROM element_spatial_watermark LIMIT 1), 0))
            """
        ) as r,
    ):
        max_sequence: SequenceId
        last_sequence: SequenceId
        max_sequence, last_sequence = await r.fetchone()  # type: ignore

    num_items = max_sequence - last_sequence
    if not num_items:
        return

    # Rollback unfinished work
    async with db(True) as conn:
        await conn.execute('TRUNCATE element_spatial_staging')
        await conn.execute('TRUNCATE element_spatial_staging_batch')
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
    depth: cython.size_t
    for depth in range(_MAX_RELATION_NESTING_DEPTH + 1):
        if not await _process_depth(
            depth=depth,
            last_sequence=last_sequence,
            max_sequence=max_sequence,
            parallelism=parallelism,
            batch_size=ways_batch_size if not depth else rels_batch_size,
        ):
            break

        # Seed pending relations for the next depth
        if depth < _MAX_RELATION_NESTING_DEPTH:
            await _seed_pending_relations(
                depth=depth,
                last_sequence=last_sequence,
                max_sequence=max_sequence,
                parallelism=parallelism,
                batch_size=ways_batch_size,
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
    """Process a single depth of element_spatial updates. Returns True if progress was made."""
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
        progress(desc=f'element_spatial_staging depth={depth}', total=num_items)
        if not last_sequence
        else nullcontext()
    ) as advance:

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
            if advance is not None:
                advance(end_seq - start_seq + 1)

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
            if advance is not None:
                advance(min(batch_size, num_items - batch_offset))

        async with TaskGroup() as tg:
            if not depth:
                # Depth 0: Batch by sequence range
                for start_seq in range(last_sequence + 1, max_sequence + 1, batch_size):
                    end_seq = min(start_seq + batch_size - 1, max_sequence)
                    tg.create_task(process_ways_batch(start_seq, end_seq))
            else:
                # Depth 1+: Batch by offset into pending_rels
                for batch_offset in range(0, num_items, batch_size):
                    tg.create_task(process_rels_batch(batch_offset))

    async with db(True) as conn:
        if num_items >= 10_000:
            await conn.execute('ANALYZE element_spatial_staging')

        if depth:
            async with await conn.execute(
                """
                SELECT COUNT(*) FROM element_spatial_staging
                WHERE depth = %s
                """,
                (depth,),
            ) as r:
                (rels_inserted,) = await r.fetchone()  # type: ignore

            if not rels_inserted:
                logging.debug('Depth %d: No more progress is being made', depth)
                return False

    return True


async def _seed_pending_relations(
    *,
    depth: int,
    last_sequence: int,
    max_sequence: int,
    parallelism: int,
    batch_size: int,
) -> None:
    """Seed pending relations using parallel batched queries to avoid array_agg overflow."""
    logging.debug('Seeding pending relations after depth %d', depth)

    async with db(True) as conn:
        if depth == 0:
            await conn.execute(
                """
                INSERT INTO element_spatial_pending_rels (typed_id)
                SELECT typed_id FROM element
                WHERE sequence_id BETWEEN %(seq_start)s AND %(seq_end)s
                  AND typed_id >= 2305843009213693952
                  AND latest
                ON CONFLICT DO NOTHING
                """,
                {'seq_start': last_sequence + 1, 'seq_end': max_sequence},
            )
        else:
            await conn.execute(
                """
                DELETE FROM element_spatial_pending_rels
                WHERE typed_id IN (
                    SELECT typed_id
                    FROM element_spatial_staging
                    WHERE depth = %(depth)s
                )
                """,
                {'depth': depth},
            )

    semaphore = Semaphore(parallelism)
    num_items = max_sequence - last_sequence

    with (
        progress(desc='element_spatial_pending_rels', total=num_items)
        if not last_sequence and not depth
        else nullcontext()
    ) as advance:

        async def seed_from_element_batch_task(seq_start: int, seq_end: int) -> None:
            await _seed_from_element_batch(seq_start, seq_end, semaphore)
            if advance is not None:
                advance(seq_end - seq_start + 1)

        async with TaskGroup() as tg:
            if depth == 0:
                # Nodes from element
                for seq_start in range(last_sequence + 1, max_sequence + 1, batch_size):
                    seq_end = min(seq_start + batch_size - 1, max_sequence)
                    tg.create_task(seed_from_element_batch_task(seq_start, seq_end))

            # Ways and relations from staging
            num_batches = await _materialize_staging_batches(
                depth=depth, batch_size=batch_size
            )
            for batch_id in range(num_batches):
                tg.create_task(_seed_from_staging_batch(batch_id, semaphore))

    async with db(True) as conn:
        await conn.execute('ANALYZE element_spatial_pending_rels')


async def _seed_from_element_batch(
    seq_start: int, seq_end: int, semaphore: Semaphore
) -> None:
    """Find relations whose members include nodes from given sequence range."""
    async with semaphore, db(True) as conn:
        await conn.execute(
            """
            INSERT INTO element_spatial_pending_rels (typed_id)
            SELECT typed_id FROM element
            WHERE members && ARRAY(
                SELECT typed_id FROM element
                WHERE sequence_id BETWEEN %(seq_start)s AND %(seq_end)s
                  AND typed_id <= 1152921504606846975
                  AND latest
              )
              AND typed_id >= 2305843009213693952
              AND latest
              AND tags IS NOT NULL
            ON CONFLICT DO NOTHING
            """,
            {'seq_start': seq_start, 'seq_end': seq_end},
        )


async def _materialize_staging_batches(
    *,
    depth: int,
    batch_size: int,
) -> int:
    """Materialize staging batches. Returns number of batches."""
    async with db(True) as conn:
        await conn.execute('TRUNCATE element_spatial_staging_batch')
        await conn.execute(
            """
            WITH staging_rows AS (
                SELECT
                    typed_id,
                    ROW_NUMBER() OVER (ORDER BY typed_id) AS rn
                FROM element_spatial_staging
                WHERE %(depth)s = 0 OR depth = %(depth)s
            ),
            batched AS (
                SELECT
                    ((rn - 1) / %(batch_size)s)::INTEGER AS batch_id,
                    ARRAY_AGG(typed_id) AS typed_ids
                FROM staging_rows
                GROUP BY batch_id
            )
            INSERT INTO element_spatial_staging_batch (batch_id, typed_ids)
            SELECT batch_id, typed_ids FROM batched
            """,
            {'depth': depth, 'batch_size': batch_size},
        )
        await conn.execute('ANALYZE element_spatial_staging_batch')

        async with await conn.execute(
            'SELECT COUNT(*) FROM element_spatial_staging_batch'
        ) as r:
            (num_batches,) = await r.fetchone()  # type: ignore
            return num_batches


async def _seed_from_staging_batch(batch_id: int, semaphore: Semaphore) -> None:
    """Find relations using pre-materialized batches."""
    async with semaphore, db(True) as conn:
        await conn.execute(
            """
            INSERT INTO element_spatial_pending_rels (typed_id)
            SELECT typed_id FROM element
            WHERE members && (
                SELECT typed_ids FROM element_spatial_staging_batch
                WHERE batch_id = %(batch_id)s
            )
              AND typed_id >= 2305843009213693952
              AND latest
              AND tags IS NOT NULL
            ON CONFLICT DO NOTHING
            """,
            {'batch_id': batch_id},
        )


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
            DELETE FROM element_spatial
            WHERE typed_id IN (
                SELECT typed_id
                FROM (
                    SELECT DISTINCT ON (typed_id) typed_id, geom
                    FROM element_spatial_staging
                    ORDER BY typed_id, updated_sequence_id DESC
                ) latest
                WHERE geom IS NULL
            )
            """
        )
        await conn.execute(
            """
            INSERT INTO element_spatial (typed_id, sequence_id, geom)
            SELECT typed_id, sequence_id, geom
            FROM (
                SELECT DISTINCT ON (typed_id) typed_id, sequence_id, geom
                FROM element_spatial_staging
                ORDER BY typed_id, updated_sequence_id DESC
            ) latest
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
        await conn.execute('TRUNCATE element_spatial_staging_batch')
        await conn.execute('TRUNCATE element_spatial_pending_rels')

    logging.debug('Finished updating element_spatial')
