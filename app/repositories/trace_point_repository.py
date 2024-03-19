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

        async with db() as session:
            stmt = (
                select(TracePoint)
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
            )
            stmt = apply_statement_context(stmt)

            union_stmt = (
                select(TracePoint)
                .join(Trace)
                .where(
                    func.ST_Intersects(TracePoint.point, geometry.wkt),
                    Trace.visibility.in_((TraceVisibility.public, TraceVisibility.private)),
                )
                .order_by(
                    TracePoint.point.asc(),
                )
            )
            union_stmt = apply_statement_context(union_stmt)

            stmt = stmt.union(union_stmt)

            if legacy_offset is not None:
                stmt = stmt.offset(legacy_offset)
            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()
