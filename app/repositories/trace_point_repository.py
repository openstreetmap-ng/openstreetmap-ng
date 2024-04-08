from collections.abc import Sequence

import numpy as np
from shapely import Point, get_coordinates
from shapely.ops import BaseGeometry
from sqlalchemy import func, select, union_all

from app.db import db
from app.lib.mercator import mercator
from app.lib.statement_context import apply_statement_context
from app.models.db.trace_ import Trace
from app.models.db.trace_point import TracePoint
from app.models.trace_visibility import TraceVisibility


# TODO: limit offset for safety
class TracePointRepository:
    @staticmethod
    async def get_many_by_trace(trace_id: int) -> Sequence[TracePoint]:
        """
        Get trace points by trace id.
        """
        async with db() as session:
            stmt = (
                select(TracePoint)
                .where(TracePoint.trace_id == trace_id)
                # this order_by is important for proper formatting
                .order_by(TracePoint.track_idx.asc(), TracePoint.captured_at.asc())
            )
            stmt = apply_statement_context(stmt)
            return (await session.scalars(stmt)).all()

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

    @staticmethod
    async def resolve_image_coords(traces: Sequence[Trace], *, limit_per_trace: int) -> None:
        """
        Resolve image coords for traces.
        """
        if not traces:
            return

        async with db() as session:
            stmts = []

            for trace in traces:
                stmt_ = (
                    select(
                        TracePoint.trace_id,
                        TracePoint.point,
                        func.row_number().over().label('row_number'),
                    )
                    .where(TracePoint.trace_id == trace.id)
                    .order_by(TracePoint.track_idx.asc(), TracePoint.captured_at.asc())
                )

                if trace.size > limit_per_trace:
                    indices = np.round(np.linspace(1, trace.size, limit_per_trace)).astype(int)
                    stmt_subq = stmt_.subquery()
                    stmt_ = (
                        stmt_subq.select()
                        .where(stmt_subq.c.row_number.in_(indices))  #
                        .order_by(stmt_subq.c.row_number)
                    )

                stmts.append(stmt_)

            stmt = union_all(*stmts)
            rows = (await session.execute(stmt)).all()

        id_points_map: dict[int, list[Point]] = {}
        for trace in traces:
            id_points_map[trace.id] = trace.image_coords = []
        for row in rows:
            id_points_map[row[0]].append(row[1])
        for trace in traces:
            if trace.size < 2:
                trace.image_coords.clear()
            else:
                coords = mercator(get_coordinates(trace.image_coords), 100, 100).astype(int).flatten().tolist()
                trace.image_coords = coords
