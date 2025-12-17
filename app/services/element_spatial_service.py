import asyncio
import logging
from asyncio import Event, Future, Semaphore, TaskGroup
from contextlib import asynccontextmanager, nullcontext
from math import ceil
from random import uniform
from time import monotonic

import cython
from psycopg.errors import InternalError_
from sentry_sdk import capture_exception
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
_AVG_MEMBERS_PER_RELATION = 15

_PROCESS_REQUEST_EVENT = Event()
_PROCESS_DONE_EVENT = Event()

# - w n: avg ways per batch
# - m node_point: avg nodes per way (LEFT JOIN hint unsupported: github.com/ossc-db/pg_hint_plan/issues/217)
_BATCH_QUERY_WAYS = """
/*+ NoSeqScan(w) Rows(w n #{ways_per_batch}) Rows(m node_point #10) */
WITH changed_node_ids AS (
    SELECT array_agg(typed_id) AS ids
    FROM element
    WHERE {include_node_overlap}
      AND sequence_id BETWEEN {start_seq} AND {end_seq}
      AND typed_id <= 1152921504606846975
      AND latest
),
candidate_ways AS (
    SELECT w.typed_id, w.sequence_id, w.members, w.visible
    FROM element w
    CROSS JOIN changed_node_ids n
    WHERE w.typed_id BETWEEN 1152921504606846976 AND 2305843009213693951
      AND w.latest
      AND (
        w.sequence_id BETWEEN {start_seq} AND {end_seq}
        OR ({include_node_overlap} AND w.members && n.ids)
      )
),
ways_with_geom AS (
    SELECT
        w.typed_id,
        w.sequence_id,
        CASE
            WHEN way_geom.npoints >= 4
             AND ST_IsClosed(way_geom.line_geom)
             AND ST_IsSimple(way_geom.line_geom)
            THEN ST_MakePolygon(way_geom.line_geom)

            WHEN way_geom.npoints >= 2
            THEN way_geom.line_geom

            ELSE NULL
        END AS geom
    FROM candidate_ways w
    LEFT JOIN LATERAL (
        SELECT COALESCE(ST_NPoints(line_geom), 0) AS npoints, line_geom
        FROM (
            SELECT ST_RemoveRepeatedPoints(
                ST_MakeLine(node_point.point ORDER BY m.ord)
                    FILTER (WHERE node_point.point IS NOT NULL)
            ) AS line_geom
            FROM UNNEST(w.members) WITH ORDINALITY AS m(node_id, ord)
            LEFT JOIN LATERAL (
                SELECT point
                FROM element n
                WHERE n.typed_id = m.node_id
                  AND n.typed_id <= 1152921504606846975
                  AND n.sequence_id <= {max_sequence}
                ORDER BY n.sequence_id DESC
                LIMIT 1
            ) node_point ON true
            WHERE w.visible
              AND w.members IS NOT NULL
        ) AS computed
    ) AS way_geom ON true
)
INSERT INTO element_spatial_staging (typed_id, sequence_id, updated_sequence_id, depth, geom)
SELECT typed_id, sequence_id, {end_seq}, 0, geom FROM ways_with_geom
"""

# - r batch_rel_ids: 1 row per relation
# - r m: avg members per batch
# - mw gl: avg members per relation (LEFT JOIN hint unsupported: github.com/ossc-db/pg_hint_plan/issues/217)
_BATCH_QUERY_RELATIONS = """
/*+ Rows(r batch_rel_ids #{batch_items}) Rows(r m #{members_per_batch}) Rows(rm rr #{members_per_batch}) Rows(mw gl #{members_per_rel}) */
WITH
batch_rel_ids AS (
    SELECT UNNEST(typed_ids) AS typed_id
    FROM element_spatial_pending_rels_batch
    WHERE batch_id = {batch_id}
),
rels_rows AS (
    SELECT
        r.typed_id,
        r.sequence_id,
        r.members,
        r.visible,
        r.tags,
        (r.visible AND r.members IS NOT NULL AND r.tags IS NOT NULL) AS eligible
    FROM element r
    INNER JOIN batch_rel_ids ON batch_rel_ids.typed_id = r.typed_id
    WHERE r.latest
      AND r.typed_id >= 2305843009213693952
),
eligible_rel_members AS (
    SELECT r.typed_id AS parent_id, m.member_id
    FROM rels_rows r
    CROSS JOIN LATERAL UNNEST(r.members) AS m(member_id)
    WHERE r.eligible
),
blocked_rel_ids AS (
    SELECT DISTINCT rm.parent_id
    FROM eligible_rel_members rm
    INNER JOIN element_spatial_pending_rels pr ON pr.typed_id = rm.member_id
    WHERE rm.member_id >= 2305843009213693952
),
ready_rels AS (
    SELECT r.* FROM rels_rows r
    LEFT JOIN blocked_rel_ids b ON b.parent_id = r.typed_id
    WHERE NOT r.eligible
       OR {depth} >= {max_depth}
       OR b.parent_id IS NULL
),
needed_member_ids AS (
    SELECT DISTINCT rm.member_id AS typed_id
    FROM eligible_rel_members rm
    INNER JOIN ready_rels rr ON rr.typed_id = rm.parent_id
    WHERE rm.member_id >= 1152921504606846976
),
staging_latest_geom AS (
    SELECT n.typed_id, s.typed_id AS staged_typed_id, s.geom
    FROM needed_member_ids n
    LEFT JOIN LATERAL (
        SELECT s.typed_id, s.geom
        FROM element_spatial_staging s
        WHERE s.typed_id = n.typed_id
          AND s.depth < {depth}
        ORDER BY s.updated_sequence_id DESC, s.depth DESC
        LIMIT 1
    ) s ON true
),
geom_lookup AS (
    -- Priority 1: Staging (current cycle, most recent)
    SELECT typed_id, geom
    FROM staging_latest_geom
    WHERE staged_typed_id IS NOT NULL
      AND geom IS NOT NULL

    UNION ALL

    -- Priority 2: Production table (previous cycles, fallback only)
    SELECT es.typed_id, es.geom
    FROM staging_latest_geom sl
    INNER JOIN element_spatial es ON es.typed_id = sl.typed_id
    WHERE sl.staged_typed_id IS NULL
),
rels_computed AS (
    SELECT
        rr.typed_id,
        rr.sequence_id,
        NULL::geometry AS geom
    FROM ready_rels rr
    WHERE NOT rr.eligible

    UNION ALL

    SELECT
        rr.typed_id,
        rr.sequence_id,
        rel_geom.geom
    FROM ready_rels rr
    LEFT JOIN LATERAL (
        WITH members_union_geom AS (
            SELECT ST_Union(COALESCE(gl.geom, node_point.point)) AS geom
            FROM UNNEST(rr.members) AS mw(member_id)
            LEFT JOIN geom_lookup gl ON gl.typed_id = mw.member_id
            LEFT JOIN LATERAL (
                SELECT point
                FROM element n
                WHERE n.typed_id = mw.member_id
                  AND n.typed_id <= 1152921504606846975
                  AND mw.member_id <= 1152921504606846975
                  AND n.sequence_id <= {max_sequence}
                ORDER BY n.sequence_id DESC
                LIMIT 1
            ) node_point ON true
        ),
        extracted_geoms AS (
            SELECT
                ST_CollectionExtract(geom, 1) AS points,
                ST_CollectionExtract(geom, 2) AS lines,
                ST_CollectionExtract(geom, 3) AS polys
            FROM members_union_geom
        ),
        lines_geom AS (
            SELECT ST_Union(
                (SELECT lines FROM extracted_geoms),
                ST_Boundary((SELECT polys FROM extracted_geoms))
            ) AS geom
        ),
        polys_geom AS (
            SELECT ST_Union(
                (SELECT ST_Polygonize(geom) FROM lines_geom),
                (SELECT polys FROM extracted_geoms)
            ) AS geom
        )
        SELECT ST_RemoveRepeatedPoints(
            ST_Collect(
                CASE
                    WHEN ST_IsEmpty((SELECT geom FROM polys_geom))
                     AND ST_IsEmpty((SELECT geom FROM lines_geom))
                    THEN NULL
                    ELSE ST_Union(
                        (SELECT geom FROM polys_geom),
                        ST_LineMerge((SELECT geom FROM lines_geom))
                    )
                END,
                CASE
                    WHEN ST_IsEmpty((SELECT points FROM extracted_geoms))
                    THEN NULL
                    ELSE (SELECT points FROM extracted_geoms)
                END
            )
        ) AS geom
    ) AS rel_geom ON true
    WHERE rr.eligible
)
INSERT INTO element_spatial_staging (typed_id, sequence_id, updated_sequence_id, depth, geom)
SELECT typed_id, sequence_id, {max_sequence}, {depth}, geom FROM rels_computed
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

                try:
                    with (
                        SENTRY_ELEMENT_SPATIAL_MONITOR,
                        start_transaction(
                            op='task', name=SENTRY_ELEMENT_SPATIAL_MONITOR_SLUG
                        ),
                    ):
                        await _update()
                except InternalError_ as e:
                    if 'GEOS Error' in str(e):
                        capture_exception(e)
                        logging.critical(
                            'ElementSpatialService encountered a GEOS error; paused indefinitely',
                            exc_info=e,
                        )
                        await Future()
                    raise

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
    ways_batch_size: int = 20_000,
    rels_batch_size: int = 1_000,
    _MAX_RELATION_NESTING_DEPTH: cython.size_t = _MAX_RELATION_NESTING_DEPTH,
) -> None:
    """
    Update the element_spatial table with geometries and spatial indices for ways and relations.

    Uses incremental processing based on sequence_id watermark. Reactively detects affected
    parent elements when members change:
    - Ways updated when: the way itself changes OR any member node changes
    - Relations updated when: the relation itself changes OR any member node/way changes
    - Initial build (watermark=0): skip node→way cascading to avoid duplicate work

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
    if num_items == 0:
        return

    # Rollback unfinished work
    async with db(True) as conn:
        await conn.execute('TRUNCATE element_spatial_staging')
        await conn.execute('TRUNCATE element_spatial_staging_batch')
        await conn.execute('TRUNCATE element_spatial_pending_rels')
        await conn.execute('TRUNCATE element_spatial_pending_rels_batch')

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
            batch_size=(ways_batch_size if depth == 0 else rels_batch_size),
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

        if num_items == 0:
            logging.debug('Depth %d: No relations to process', depth)
            return False

        logging.debug('Depth %d: Processing %d relations', depth, num_items)
        rels_num_batches = await _materialize_pending_rels_batches(batch_size)
        rels_last_batch_size = num_items - (batch_size * (rels_num_batches - 1))
    else:
        num_items = max_sequence - last_sequence
        logging.debug('Depth 0: Processing %d changes', num_items)
        rels_num_batches = 0
        rels_last_batch_size = 0

    semaphore = Semaphore(parallelism)
    include_node_overlap = 'TRUE' if last_sequence else 'FALSE'

    with (
        progress(desc=f'element_spatial_staging depth={depth}', total=num_items)
        if last_sequence == 0
        else nullcontext()
    ) as advance:

        async def process_ways_batch(start_seq: int, end_seq: int):
            batch_items = end_seq - start_seq + 1
            ways_per_batch = (batch_items + 4) // 5
            async with semaphore, db(True) as conn:
                await conn.execute(
                    _BATCH_QUERY_WAYS.format(  # type: ignore
                        ways_per_batch=ways_per_batch,
                        start_seq=start_seq,
                        end_seq=end_seq,
                        max_sequence=max_sequence,
                        include_node_overlap=include_node_overlap,
                    )
                )
            if advance is not None:
                advance(batch_items)

        async def process_rels_batch(batch_id: int, batch_items: int):
            async with semaphore, db(True) as conn:
                await conn.execute(
                    _BATCH_QUERY_RELATIONS.format(  # type: ignore
                        members_per_rel=_AVG_MEMBERS_PER_RELATION,
                        members_per_batch=batch_items * _AVG_MEMBERS_PER_RELATION,
                        depth=depth,
                        max_depth=_MAX_RELATION_NESTING_DEPTH,
                        max_sequence=max_sequence,
                        batch_id=batch_id,
                        batch_items=batch_items,
                    )
                )
            if advance is not None:
                advance(batch_items)

        async with TaskGroup() as tg:
            if depth == 0:
                # Depth 0: Batch by sequence range
                for start_seq in range(last_sequence + 1, max_sequence + 1, batch_size):
                    end_seq = min(start_seq + batch_size - 1, max_sequence)
                    tg.create_task(process_ways_batch(start_seq, end_seq))
            else:
                # Depth 1+: Batch by pre-materialized batch_id
                for batch_id in range(rels_num_batches):
                    batch_items = (
                        rels_last_batch_size
                        if batch_id == (rels_num_batches - 1)
                        else batch_size
                    )
                    tg.create_task(process_rels_batch(batch_id, batch_items))

    async with db(True) as conn:
        if depth == 0:
            if num_items >= 10_000:
                await conn.execute('ANALYZE element_spatial_staging')

        else:
            async with await conn.execute(
                """
                SELECT COUNT(*) FROM element_spatial_staging
                WHERE depth = %s
                """,
                (depth,),
            ) as r:
                (rels_inserted,) = await r.fetchone()  # type: ignore
                if rels_inserted == 0:
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

        # Initial build (watermark=0): pending already contains all latest relations via the
        # sequence-range insert above. Additional parent discovery via members overlap
        # adds no new work and is extremely expensive at full scale.
        if last_sequence == 0:
            await conn.execute('ANALYZE element_spatial_pending_rels')
            return

    semaphore = Semaphore(parallelism)
    num_items = max_sequence - last_sequence

    with (
        progress(desc='element_spatial_pending_rels', total=num_items)
        if last_sequence == 0 and depth == 0
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
            num_batches = await _materialize_staging_batches(batch_size, depth=depth)
            for batch_id in range(num_batches):
                tg.create_task(_seed_from_staging_batch(batch_id, semaphore))

    if depth == 0:
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


async def _materialize_staging_batches(batch_size: int, *, depth: int) -> int:
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

        async with await conn.execute(
            'SELECT COUNT(*) FROM element_spatial_staging_batch'
        ) as r:
            (num_batches,) = await r.fetchone()  # type: ignore
            return num_batches


async def _materialize_pending_rels_batches(batch_size: int) -> int:
    """Materialize pending relation batches. Returns number of batches."""
    async with db(True) as conn:
        await conn.execute('TRUNCATE element_spatial_pending_rels_batch')
        await conn.execute(
            """
            WITH pending_rows AS (
                SELECT
                    typed_id,
                    ROW_NUMBER() OVER (ORDER BY typed_id) AS rn
                FROM element_spatial_pending_rels
            ),
            batched AS (
                SELECT
                    ((rn - 1) / %(batch_size)s)::INTEGER AS batch_id,
                    ARRAY_AGG(typed_id) AS typed_ids
                FROM pending_rows
                GROUP BY batch_id
            )
            INSERT INTO element_spatial_pending_rels_batch (batch_id, typed_ids)
            SELECT batch_id, typed_ids FROM batched
            """,
            {'batch_size': batch_size},
        )

        async with await conn.execute(
            'SELECT COUNT(*) FROM element_spatial_pending_rels_batch'
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
            if last_sequence == 0
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
                    ORDER BY typed_id, updated_sequence_id DESC, depth DESC
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
                ORDER BY typed_id, updated_sequence_id DESC, depth DESC
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
        await conn.execute('TRUNCATE element_spatial_pending_rels_batch')

    logging.debug('Finished updating element_spatial')
