from shapely import LineString, Polygon

from app.db import db_fetchcol


class GPSTileQuery:
    @staticmethod
    async def find_lines(bounds: Polygon) -> list[LineString]:
        """Fetch public geometry, including edges with both endpoints outside.

        Bound work to 500 recent candidate traces and 100,000 visible edges.
        Dumping individual edges also allows date-line crossings to follow the
        short path, rather than painting a spurious line across the whole world.
        No trace metadata or owner-dependent visibility is exposed.
        """
        return await db_fetchcol(
            LineString,
            t"""
                WITH candidates AS MATERIALIZED (
                    SELECT segments FROM trace
                    WHERE visibility IN ('public', 'identifiable')
                    AND (
                        segments && {bounds}
                        OR ST_ShiftLongitude(segments) && {bounds}
                        OR ST_ShiftLongitude(segments) && ST_Translate({bounds}, 360, 0)
                    )
                    ORDER BY id DESC
                    LIMIT 500
                ), edges AS (
                    SELECT CASE
                        WHEN abs(ST_X(ST_StartPoint(edge.geom))
                               - ST_X(ST_EndPoint(edge.geom))) > 180
                        THEN ST_ShiftLongitude(edge.geom)
                        ELSE edge.geom
                    END AS geom
                    FROM candidates
                    CROSS JOIN LATERAL ST_DumpSegments(segments) AS edge
                )
                SELECT clipped.geom
                FROM edges
                CROSS JOIN (VALUES (-360), (0), (360)) AS offsets(dx)
                CROSS JOIN LATERAL (
                    SELECT ST_Translate(edges.geom, offsets.dx, 0) AS geom
                ) AS shifted
                CROSS JOIN LATERAL (
                    SELECT ST_ClipByBox2D(shifted.geom, box2d({bounds})) AS geom
                ) AS clipped
                WHERE shifted.geom && {bounds}
                AND ST_Intersects(shifted.geom, {bounds})
                AND NOT ST_IsEmpty(clipped.geom)
                LIMIT 100000
            """,
        )
