from collections.abc import Sequence

from shapely import Polygon
from sqlalchemy import func, select

from app.db import db
from app.lib.joinedload_context import get_joinedload
from app.models.db.trace_ import Trace
from app.models.db.trace_point import TracePoint
from app.models.trace_visibility import TraceVisibility


# TODO: limit offset for safety
class TracePointRepository:
    @staticmethod
    async def find_many_by_geometry(
        geometry: Polygon,
        *,
        limit: int | None,
        legacy_offset: int | None = None,
    ) -> Sequence[TracePoint]:
        """
        Find trace points by geometry.
        """

        async with db() as session:
            stmt = (
                select(TracePoint)
                .options(get_joinedload())
                .join(Trace)
                .where(
                    func.ST_Intersects(TracePoint.point, geometry.wkt),
                    Trace.visibility.in_((TraceVisibility.identifiable, TraceVisibility.trackable)),
                )
                .order_by(
                    TracePoint.trace_id.desc(),
                    TracePoint.track_idx.asc(),
                    TracePoint.captured_at.asc(),
                )
            ).union(
                select(TracePoint)
                .options(get_joinedload())
                .join(Trace)
                .where(
                    func.ST_Intersects(TracePoint.point, geometry.wkt),
                    Trace.visibility.in_((TraceVisibility.public, TraceVisibility.private)),
                )
                .order_by(
                    TracePoint.point.asc(),
                )
            )

            if legacy_offset is not None:
                stmt = stmt.offset(legacy_offset)
            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()
