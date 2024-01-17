from collections.abc import Sequence

from shapely import Polygon
from sqlalchemy import func, select

from src.db import DB
from src.lib_cython.joinedload_context import get_joinedload
from src.limits import FIND_LIMIT
from src.models.db.trace_ import Trace
from src.models.db.trace_point import TracePoint
from src.models.trace_visibility import TraceVisibility


# TODO: limit offset for safety
class TracePointRepository:
    @staticmethod
    async def find_many_by_geometry(
        geometry: Polygon,
        *,
        limit: int | None = FIND_LIMIT,
        legacy_offset: int | None = None,
    ) -> Sequence[TracePoint]:
        """
        Find trace points by geometry.
        """

        async with DB() as session:
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
