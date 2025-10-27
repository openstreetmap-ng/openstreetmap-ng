from psycopg.rows import dict_row
from shapely.geometry.base import BaseGeometry

from app.config import QUERY_FEATURES_RESULTS_LIMIT
from app.db import db
from app.models.db.element_spatial import ElementSpatial


class ElementSpatialQuery:
    @staticmethod
    async def query_features(
        search_area: BaseGeometry, h3_cells: list[str]
    ) -> list[ElementSpatial]:
        """Query for elements intersecting the search area."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                (
                    SELECT
                        es.typed_id,
                        es.sequence_id,
                        es.geom,
                        es.bounds_area,
                        e.version,
                        e.tags
                    FROM element_spatial es
                    INNER JOIN element e ON e.typed_id = es.typed_id AND e.latest
                    WHERE h3_geometry_to_compact_cells(es.geom, 11) && %(h3_cells)s::h3index[]
                        AND ST_Intersects(es.geom, %(area)s)
                    ORDER BY es.bounds_area, es.typed_id DESC
                    LIMIT %(limit)s
                )
                UNION ALL
                (
                    SELECT
                        e.typed_id,
                        e.sequence_id,
                        e.point AS geom,
                        0 AS bounds_area,
                        e.version,
                        e.tags
                    FROM element e
                    WHERE e.typed_id <= 1152921504606846975
                        AND e.latest
                        AND e.visible
                        AND e.tags IS NOT NULL
                        AND e.point IS NOT NULL
                        AND ST_Intersects(e.point, %(area)s)
                    ORDER BY bounds_area, e.typed_id DESC
                    LIMIT %(limit)s
                )
                ORDER BY bounds_area, typed_id DESC
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
