from shapely import MultiPolygon, Polygon

from app.config import QUERY_FEATURES_RESULTS_LIMIT
from app.db import db_fetchall
from app.lib.geo.h3 import polygon_to_h3_search
from app.models.db.element_spatial import ElementSpatial


class ElementSpatialQuery:
    @staticmethod
    async def query_features(
        search_area: Polygon | MultiPolygon,
    ) -> list[ElementSpatial]:
        """Query for elements intersecting the search area."""
        h3_cells = polygon_to_h3_search(search_area, 10)
        limit = QUERY_FEATURES_RESULTS_LIMIT

        return await db_fetchall(
            ElementSpatial,
            t"""
            WITH area_center AS (
                SELECT
                    ST_X(ST_Centroid({search_area})) AS cx,
                    ST_Y(ST_Centroid({search_area})) AS cy
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
                WHERE h3_geometry_to_compact_cells(es.geom, 10) && {h3_cells}::h3index[]
                    AND ST_Intersects(es.geom, {search_area})

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
                    AND ST_Intersects(e.point, {search_area})
            ) combined
            ORDER BY sort_key
            LIMIT {limit}
            """,
        )
