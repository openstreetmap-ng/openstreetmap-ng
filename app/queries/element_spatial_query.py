from psycopg.rows import dict_row
from shapely import MultiPolygon, Polygon

from app.config import QUERY_FEATURES_RESULTS_LIMIT
from app.db import db
from app.lib.geo_utils import polygon_to_h3_search
from app.models.db.element_spatial import ElementSpatial


class ElementSpatialQuery:
    @staticmethod
    async def query_features(
        search_area: Polygon | MultiPolygon,
    ) -> list[ElementSpatial]:
        """Query for elements intersecting the search area."""
        h3_cells = polygon_to_h3_search(search_area, 10)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                WITH area_center AS (
                    SELECT
                        ST_X(ST_Centroid(%(area)s)) AS cx,
                        ST_Y(ST_Centroid(%(area)s)) AS cy
                )
                SELECT typed_id, sequence_id, geom, version, tags
                FROM (
                    SELECT
                        es.typed_id,
                        es.sequence_id,
                        es.geom,
                        e.version,
                        e.tags,
                        es.bounds_area AS sort_key
                    FROM element_spatial es
                    INNER JOIN element e ON e.typed_id = es.typed_id
                        AND e.typed_id >= 1152921504606846976
                        AND e.latest
                    WHERE h3_geometry_to_compact_cells(es.geom, 10) && %(h3_cells)s::h3index[]
                        AND ST_Intersects(es.geom, %(area)s)

                    UNION ALL

                    SELECT
                        e.typed_id,
                        e.sequence_id,
                        e.point AS geom,
                        e.version,
                        e.tags,
                        (ST_X(e.point) - area_center.cx) * (ST_X(e.point) - area_center.cx)
                        + (ST_Y(e.point) - area_center.cy) * (ST_Y(e.point) - area_center.cy) AS sort_key
                    FROM element e, area_center
                    WHERE e.typed_id <= 1152921504606846975
                        AND e.latest
                        AND e.visible
                        AND e.tags IS NOT NULL
                        AND e.point IS NOT NULL
                        AND ST_Intersects(e.point, %(area)s)
                ) combined
                ORDER BY sort_key
                LIMIT %(limit)s
                """,
                {
                    'area': search_area,
                    'h3_cells': h3_cells,
                    'limit': QUERY_FEATURES_RESULTS_LIMIT,
                },
            ) as r,
        ):
            return await r.fetchall()  # type: ignore
