from psycopg import AsyncConnection
from shapely import MultiLineString

from app.db import db, db_fetchrows, db_fetchval
from app.lib.geo.gps_tiles import GPS_MASTER_ZOOM
from app.models.types import TraceId
from speedup import gps_trace_pixel_batches


class GPSTileService:
    @staticmethod
    async def insert(trace_id: TraceId, conn: AsyncConnection):
        # Read quantized geometry, not the pre-insert upload representation.
        segments = await db_fetchval(
            MultiLineString,
            t'SELECT segments FROM trace WHERE id = {trace_id} FOR UPDATE',
            conn=conn,
        )
        if segments is None:
            return
        if (
            await db_fetchval(
                int,
                t'SELECT trace_id FROM gps_trace_index WHERE trace_id = {trace_id}',
                conn=conn,
            )
            is not None
        ):
            return
        batches = gps_trace_pixel_batches(
            [list(segment.coords) for segment in segments.geoms], GPS_MASTER_ZOOM
        )
        # Serialize counter mutations until finer-grained locking is proven safe.
        await conn.execute(t'SELECT pg_advisory_xact_lock(108, 0)')
        for pixels in batches:
            xs, ys = map(list, zip(*pixels, strict=True))
            await conn.execute(t"""
                WITH added AS (
                    INSERT INTO gps_trace_pixel (trace_id, x, y)
                    SELECT {trace_id}, x, y FROM unnest({xs}::integer[], {ys}::integer[]) AS p(x, y)
                    ON CONFLICT DO NOTHING
                    RETURNING x, y
                ), master AS (
                    INSERT INTO gps_pixel (x, y, count)
                    SELECT x, y, 1 FROM added
                    ON CONFLICT (x, y) DO UPDATE SET count = gps_pixel.count + 1
                )
                INSERT INTO gps_pixel_overview (zoom, x, y, count)
                SELECT z, x >> ({GPS_MASTER_ZOOM} - z), y >> ({GPS_MASTER_ZOOM} - z), count(*)
                FROM added CROSS JOIN generate_series(0, {GPS_MASTER_ZOOM} - 1) AS z
                GROUP BY 1, 2, 3
                ON CONFLICT (zoom, x, y) DO UPDATE SET count = gps_pixel_overview.count + EXCLUDED.count
            """)
        await conn.execute(
            t'INSERT INTO gps_trace_index (trace_id) VALUES ({trace_id})'
        )

    @staticmethod
    async def backfill(limit: int = 1000):
        if not 1 <= limit <= 10000:
            raise ValueError('Backfill limit must be between 1 and 10000')
        rows = await db_fetchrows(t"""
            SELECT id FROM trace
            WHERE NOT EXISTS (
                SELECT 1 FROM gps_trace_index WHERE trace_id = trace.id
            )
            ORDER BY id LIMIT {limit}
        """)
        for (trace_id,) in rows:
            async with db(True) as conn:
                await GPSTileService.insert(trace_id, conn)

    @staticmethod
    async def delete(trace_id: TraceId, conn: AsyncConnection):
        await conn.execute(t'SELECT pg_advisory_xact_lock(108, 0)')
        await conn.execute(t"""
            WITH removed AS (
                SELECT x, y FROM gps_trace_pixel WHERE trace_id = {trace_id}
            ), master AS (
                UPDATE gps_pixel AS p SET count = p.count - 1
                FROM removed AS r WHERE p.x = r.x AND p.y = r.y
            ), overview AS (
                SELECT z, x >> ({GPS_MASTER_ZOOM} - z) AS x,
                    y >> ({GPS_MASTER_ZOOM} - z) AS y, count(*) AS count
                FROM removed CROSS JOIN generate_series(0, {GPS_MASTER_ZOOM} - 1) AS z
                GROUP BY 1, 2, 3
            )
            UPDATE gps_pixel_overview AS p SET count = p.count - r.count
            FROM overview AS r WHERE p.zoom = r.z AND p.x = r.x AND p.y = r.y
        """)
        # Keep contributions until all touched zero counters have been pruned.
        await conn.execute(t"""
            DELETE FROM gps_pixel WHERE count = 0 AND (x, y) IN (
                SELECT x, y FROM gps_trace_pixel WHERE trace_id = {trace_id}
            )
        """)
        await conn.execute(t"""
            DELETE FROM gps_pixel_overview WHERE count = 0 AND (zoom, x, y) IN (
                SELECT z, x >> ({GPS_MASTER_ZOOM} - z), y >> ({GPS_MASTER_ZOOM} - z)
                FROM gps_trace_pixel
                CROSS JOIN generate_series(0, {GPS_MASTER_ZOOM} - 1) AS z
                WHERE trace_id = {trace_id}
            )
        """)
        await conn.execute(t'DELETE FROM gps_trace_pixel WHERE trace_id = {trace_id}')
        await conn.execute(t'DELETE FROM gps_trace_index WHERE trace_id = {trace_id}')
