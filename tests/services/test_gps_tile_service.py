from contextlib import asynccontextmanager

from app.db import db, db_fetchval
from app.lib.geo.gps_tiles import GPS_MASTER_ZOOM
from app.models.types import TraceId
from app.services.gps_tile_service import GPSTileService


@asynccontextmanager
async def _rollback_connection():
    async with db(True) as conn, conn.transaction(force_rollback=True):
        yield conn


async def _seed(conn, ids: list[int], x: int, y: int):
    size = len(ids)
    await conn.execute(t'SELECT pg_advisory_xact_lock(108, 0)')
    await conn.execute(t"""
        INSERT INTO gps_trace_pixel (trace_id, x, y)
        SELECT id, {x}, {y} FROM unnest({ids}::bigint[]) AS id
    """)
    await conn.execute(t"""
        INSERT INTO gps_pixel (x, y, count) VALUES ({x}, {y}, {size})
        ON CONFLICT (x, y) DO UPDATE SET count = gps_pixel.count + EXCLUDED.count
    """)
    await conn.execute(t"""
        INSERT INTO gps_pixel_overview (zoom, x, y, count)
        SELECT z, {x} >> ({GPS_MASTER_ZOOM} - z), {y} >> ({GPS_MASTER_ZOOM} - z), {size}
        FROM generate_series(0, {GPS_MASTER_ZOOM} - 1) AS z
        ON CONFLICT (zoom, x, y) DO UPDATE SET count = gps_pixel_overview.count + EXCLUDED.count
    """)


async def test_delete_keeps_overlapping_contribution():
    async with _rollback_connection() as conn:
        await _seed(conn, [-10801, -10802], 42, 42)
        before = await db_fetchval(
            int, t'SELECT count FROM gps_pixel WHERE x = 42 AND y = 42', conn=conn
        )
        await GPSTileService.delete(TraceId(-10801), conn)
        assert (
            await db_fetchval(
                int, t'SELECT count FROM gps_pixel WHERE x = 42 AND y = 42', conn=conn
            )
            == before - 1
        )
        await GPSTileService.delete(TraceId(-10801), conn)
        assert (
            await db_fetchval(
                int, t'SELECT count FROM gps_pixel WHERE x = 42 AND y = 42', conn=conn
            )
            == before - 1
        )


async def test_counter_mutation_rolls_back():
    async with _rollback_connection() as conn:
        await _seed(conn, [-10803], 43, 43)
        before = await db_fetchval(
            int, t'SELECT count FROM gps_pixel WHERE x = 43 AND y = 43', conn=conn
        )
        async with conn.transaction(force_rollback=True):
            await GPSTileService.delete(TraceId(-10803), conn)
        assert (
            await db_fetchval(
                int,
                t'SELECT count(*) FROM gps_trace_pixel WHERE trace_id = -10803',
                conn=conn,
            )
            == 1
        )
        assert (
            await db_fetchval(
                int, t'SELECT count FROM gps_pixel WHERE x = 43 AND y = 43', conn=conn
            )
            == before
        )


async def test_last_contribution_prunes_only_touched_zero_counters():
    async with _rollback_connection() as conn:
        baseline = await db_fetchval(
            int,
            t'SELECT COALESCE((SELECT count FROM gps_pixel WHERE x = 44 AND y = 44), 0)',
            conn=conn,
        )
        await _seed(conn, [-10804], 44, 44)
        await GPSTileService.delete(TraceId(-10804), conn)
        remaining = await db_fetchval(
            int, t'SELECT count FROM gps_pixel WHERE x = 44 AND y = 44', conn=conn
        )
        if baseline:
            assert remaining == baseline
        else:
            assert remaining is None
        assert (
            await db_fetchval(
                int,
                t'SELECT count(*) FROM gps_trace_pixel WHERE trace_id = -10804',
                conn=conn,
            )
            == 0
        )
