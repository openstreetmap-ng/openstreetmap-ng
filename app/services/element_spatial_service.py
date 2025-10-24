import asyncio
import logging
from asyncio import Event, Semaphore, TaskGroup
from contextlib import asynccontextmanager, nullcontext
from math import ceil
from random import uniform
from time import monotonic

from psycopg.sql import SQL
from sentry_sdk.api import start_transaction
from tqdm import tqdm

from app.db import db, db_lock
from app.lib.retry import retry
from app.lib.sentry import (
    SENTRY_ELEMENT_SPATIAL_MONITOR,
    SENTRY_ELEMENT_SPATIAL_MONITOR_SLUG,
)
from app.lib.testmethod import testmethod
from app.utils import calc_num_workers

_PROCESS_REQUEST_EVENT = Event()
_PROCESS_DONE_EVENT = Event()

_BATCH_QUERY = SQL("""
WITH
changed_nodes AS (
    SELECT typed_id
    FROM (
        SELECT DISTINCT ON (typed_id) typed_id, latest
        FROM element
        WHERE sequence_id BETWEEN %(start_seq)s AND %(end_seq)s
            AND typed_id <= 1152921504606846975
        ORDER BY typed_id DESC, sequence_id DESC
    ) e
    WHERE latest
),
changed_nodes_array AS (
    SELECT array_agg(typed_id) AS typed_ids FROM changed_nodes
),
affected_ways AS (
    -- Part 1: Existing ways whose member nodes changed
    SELECT w.typed_id, w.sequence_id
    FROM element w
    CROSS JOIN changed_nodes_array
    WHERE w.typed_id BETWEEN 1152921504606846976 AND 2305843009213693951
        AND w.members && changed_nodes_array.typed_ids
        AND w.latest

    UNION

    -- Part 2: New ways or ways that changed directly
    SELECT typed_id, sequence_id
    FROM (
        SELECT DISTINCT ON (typed_id) typed_id, sequence_id, latest
        FROM element
        WHERE sequence_id BETWEEN %(start_seq)s AND %(end_seq)s
            AND typed_id BETWEEN 1152921504606846976 AND 2305843009213693951
        ORDER BY typed_id DESC, sequence_id DESC
    ) e
    WHERE latest
),
way_geoms AS (
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
    INNER JOIN affected_ways ON affected_ways.sequence_id = w.sequence_id
    LEFT JOIN LATERAL (
        SELECT ST_MakeLine(latest.point ORDER BY m.ord) AS line_geom
        FROM UNNEST(w.members) WITH ORDINALITY AS m(node_id, ord)
        LEFT JOIN LATERAL (
            SELECT point
            FROM element n
            WHERE n.typed_id = m.node_id
            ORDER BY n.sequence_id DESC
            LIMIT 1
        ) latest ON true
        WHERE w.visible AND w.tags IS NOT NULL
    ) AS way_geom ON true
),
changed_members_array AS (
    SELECT array_agg(typed_id) AS typed_ids FROM (
        SELECT typed_id FROM changed_nodes
        UNION ALL
        SELECT typed_id FROM affected_ways
    ) sub
),
affected_rels_seed AS (
    -- Part 1: Existing relations whose members changed
    SELECT r.typed_id, r.sequence_id
    FROM element r
    CROSS JOIN changed_members_array
    WHERE r.typed_id >= 2305843009213693952
        AND r.members && changed_members_array.typed_ids
        AND r.latest

    UNION

    -- Part 2: New relations or relations that changed directly
    SELECT typed_id, sequence_id
    FROM (
        SELECT DISTINCT ON (typed_id) typed_id, sequence_id, latest
        FROM element
        WHERE sequence_id BETWEEN %(start_seq)s AND %(end_seq)s
            AND typed_id >= 2305843009213693952
        ORDER BY typed_id DESC, sequence_id DESC
    ) e
    WHERE latest
),
affected_rels_seed_array AS (
    SELECT array_agg(typed_id) AS typed_ids
    FROM affected_rels_seed
),
affected_rels AS (
    SELECT typed_id, sequence_id
    FROM affected_rels_seed

    UNION

    SELECT r.typed_id, r.sequence_id
    FROM element r
    CROSS JOIN affected_rels_seed_array
    WHERE r.typed_id >= 2305843009213693952
        AND r.latest
        AND r.visible
        AND r.tags IS NOT NULL
        AND r.members && affected_rels_seed_array.typed_ids
),
rel_geoms AS (
    SELECT
        r.typed_id,
        r.sequence_id,
        rel_geom.geom
    FROM element r
    INNER JOIN affected_rels ON affected_rels.sequence_id = r.sequence_id
    LEFT JOIN LATERAL (
        WITH members_geom AS (
            SELECT ST_Collect(val) AS geom
            FROM (
                -- Direct members (nodes/ways)
                SELECT CASE WHEN wg.typed_id IS NOT NULL THEN wg.geom ELSE COALESCE(es.geom, latest.point) END AS val
                FROM UNNEST(r.members) AS m(member_id)
                LEFT JOIN way_geoms wg ON wg.typed_id = m.member_id
                LEFT JOIN element_spatial es ON es.typed_id = m.member_id
                    AND wg.typed_id IS NULL
                LEFT JOIN LATERAL (
                    SELECT point
                    FROM element e
                    WHERE e.typed_id = m.member_id
                    ORDER BY e.sequence_id DESC
                    LIMIT 1
                ) latest ON m.member_id <= 1152921504606846975
                WHERE m.member_id <= 2305843009213693951

                UNION ALL

                -- Nested relation members (relation → relation → node/way)
                SELECT CASE WHEN wg.typed_id IS NOT NULL THEN wg.geom ELSE COALESCE(es.geom, latest.point) END AS val
                FROM UNNEST(r.members) AS m(rel_id)
                INNER JOIN LATERAL (
                    SELECT members
                    FROM element child
                    WHERE child.typed_id = m.rel_id
                    ORDER BY child.sequence_id DESC
                    LIMIT 1
                ) child ON true
                CROSS JOIN UNNEST(child.members) AS m2(member_id)
                LEFT JOIN way_geoms wg ON wg.typed_id = m2.member_id
                LEFT JOIN element_spatial es ON es.typed_id = m2.member_id
                    AND wg.typed_id IS NULL
                LEFT JOIN LATERAL (
                    SELECT point
                    FROM element e
                    WHERE e.typed_id = m2.member_id
                    ORDER BY e.sequence_id DESC
                    LIMIT 1
                ) latest ON m2.member_id <= 1152921504606846975
                WHERE m.rel_id >= 2305843009213693952
            ) members_geoms
        ), noded AS (
            SELECT ST_UnaryUnion(ST_Collect(
                ST_CollectionExtract(members_geom.geom, 2),
                ST_Boundary(ST_CollectionExtract(members_geom.geom, 3))
            )) AS geom
            FROM members_geom
        ), polygons AS (
            SELECT ST_UnaryUnion(ST_Collect(
                ST_CollectionExtract(ST_Polygonize((SELECT geom FROM noded)), 3),
                ST_CollectionExtract((SELECT geom FROM members_geom), 3)
            )) AS geom
        )
        SELECT ST_RemoveRepeatedPoints(
            ST_QuantizeCoordinates(
                ST_Collect(
                    CASE
                        WHEN ST_IsEmpty((SELECT geom FROM polygons)) AND ST_IsEmpty((SELECT geom FROM noded)) THEN NULL
                        ELSE ST_UnaryUnion(ST_Collect((SELECT geom FROM polygons), ST_LineMerge((SELECT geom FROM noded))))
                    END,
                    CASE
                        WHEN ST_IsEmpty(ST_CollectionExtract((SELECT geom FROM members_geom), 1)) THEN NULL
                        ELSE ST_CollectionExtract((SELECT geom FROM members_geom), 1)
                    END
                ),
                7
            )
        ) AS geom
        WHERE r.visible AND r.tags IS NOT NULL
    ) AS rel_geom ON true
)
INSERT INTO element_spatial_staging (typed_id, sequence_id, updated_sequence_id, geom)
SELECT typed_id, sequence_id, %(end_seq)s AS updated_sequence_id, geom
FROM way_geoms
UNION ALL
SELECT typed_id, sequence_id, %(end_seq)s AS updated_sequence_id, geom
FROM rel_geoms
""")


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
    batch_size: int = 100_000,
) -> None:
    """
    Update the element_spatial table with geometries and spatial indices for ways and relations.

    Uses incremental processing based on sequence_id watermark. Reactively detects affected
    parent elements when members change:
    - Ways updated when: the way itself changes OR any member node changes
    - Relations updated when: the relation itself changes OR any member node/way changes
        (includes detecting when member ways had node changes, but excludes relation→relation
        cascades for performance)

    Two-phase approach to enable deadlock-free parallel processing:
    1. Parallel batches write to element_spatial_staging (append-only, zero conflicts)
    2. Single merge transfers staging → element_spatial:
       - DELETE elements where staging has NULL geom (invisible/untagged elements)
       - INSERT/UPDATE elements with valid geometries via INSERT ON CONFLICT
       - WHERE clause ensures only newer updates win; deduplicates staging efficiently

    This ensures element_spatial stays current without requiring synchronous updates during edits.
    """
    async with (
        db() as conn,
        await conn.execute("""
            SELECT COALESCE(MAX(sequence_id), 0) FROM element
            UNION ALL
            SELECT COALESCE(MAX(updated_sequence_id), 0) FROM element_spatial
        """) as r,
    ):
        (max_sequence,), (last_sequence,) = await r.fetchall()

    num_items = max_sequence - last_sequence
    if not num_items:
        return

    parallelism = calc_num_workers(parallelism if last_sequence else parallelism_init)
    semaphore = Semaphore(parallelism)
    num_batches = ceil(num_items / batch_size)
    logging.debug(
        'Updating element_spatial (batches=%d, parallelism=%d, sequence_id=%d..%d)',
        num_batches,
        parallelism,
        last_sequence + 1,
        max_sequence,
    )

    async with db(True) as conn:
        await conn.execute('TRUNCATE element_spatial_staging')

    with (
        nullcontext()
        if last_sequence
        else tqdm(desc='element_spatial_staging', total=num_items) as pbar
    ):

        async def process_batch(start_seq: int, end_seq: int):
            async with semaphore, db(True) as conn:
                await conn.execute(
                    _BATCH_QUERY,
                    {'start_seq': start_seq, 'end_seq': end_seq},
                )
            if pbar is not None:
                pbar.update(end_seq - start_seq + 1)

        async with TaskGroup() as tg:
            for end_seq in range(max_sequence, last_sequence, -batch_size):
                start_seq = max(end_seq - batch_size + 1, last_sequence + 1)
                tg.create_task(process_batch(start_seq, end_seq))

    logging.debug('Applying element_spatial_staging updates')

    async with db(True) as conn:
        await conn.execute("""
            MERGE INTO element_spatial AS t
            USING (
                SELECT DISTINCT ON (typed_id)
                    typed_id, sequence_id, updated_sequence_id, geom
                FROM element_spatial_staging
                ORDER BY typed_id, updated_sequence_id DESC
            ) AS s
            ON (t.typed_id = s.typed_id)
            WHEN MATCHED AND s.geom IS NULL THEN
                DELETE
            WHEN MATCHED AND s.geom IS NOT NULL AND s.updated_sequence_id > t.updated_sequence_id THEN
                UPDATE SET
                    sequence_id = s.sequence_id,
                    updated_sequence_id = s.updated_sequence_id,
                    geom = s.geom
            WHEN NOT MATCHED AND s.geom IS NOT NULL THEN
                INSERT (typed_id, sequence_id, updated_sequence_id, geom)
                VALUES (s.typed_id, s.sequence_id, s.updated_sequence_id, s.geom);
        """)
        await conn.execute('TRUNCATE element_spatial_staging')

    logging.debug('Finished updating element_spatial')
