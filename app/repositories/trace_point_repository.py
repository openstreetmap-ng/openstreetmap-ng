from collections.abc import Sequence

from shapely.ops import BaseGeometry
from sqlalchemy import func, select

from app.db import db
from app.lib.statement_context import apply_statement_context
from app.models.db.trace_ import Trace
from app.models.db.trace_point import TracePoint
from app.models.trace_visibility import TraceVisibility


# TODO: limit offset for safety
class TracePointRepository:
    @staticmethod
    async def find_many_by_geometry(
        geometry: BaseGeometry,
        *,
        limit: int | None,
        legacy_offset: int | None = None,
    ) -> Sequence[TracePoint]:
        """
        Find trace points by geometry.
        """

        geometry_wkt = 'SRID=4326;' + geometry.wkt

        async with db() as session:
            stmt1 = (
                select(TracePoint)
                .where(
                    func.ST_Intersects(TracePoint.point, geometry_wkt),
                    Trace.visibility.in_((TraceVisibility.identifiable, TraceVisibility.trackable)),
                )
                .order_by(
                    TracePoint.trace_id.desc(),
                    TracePoint.track_idx.asc(),
                    TracePoint.captured_at.asc(),
                )
            )
            stmt1 = apply_statement_context(stmt1)
            stmt2 = (
                select(TracePoint)
                .where(
                    func.ST_Intersects(TracePoint.point, geometry_wkt),
                    Trace.visibility.in_((TraceVisibility.public, TraceVisibility.private)),
                )
                .order_by(
                    TracePoint.point.asc(),
                )
            )
            stmt2 = apply_statement_context(stmt2)
            stmt = stmt1.union(stmt2)

            if legacy_offset is not None:
                stmt = stmt.offset(legacy_offset)
            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()
