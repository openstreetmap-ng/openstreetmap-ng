from collections.abc import Sequence
from typing import Type

import numpy as np
from shapely import Point, lib
from shapely.ops import BaseGeometry
from sqlalchemy import func, select, union_all

from app.db import db
from app.lib.mercator import mercator
from app.lib.options_context import apply_options_context
from app.models.db.trace_ import Trace
from app.models.db.trace_point import TracePoint


# TODO: limit offset for safety
class TracePointQuery:
    @staticmethod
    async def get_many_by_trace_id(trace_id: int) -> Sequence[TracePoint]:
        """
        Get trace points by trace id.
        """
        async with db() as session:
            stmt = (
                select(TracePoint).where(TracePoint.trace_id == trace_id)
                # this order_by is important for proper formatting
                .order_by(TracePoint.track_idx.asc(), TracePoint.captured_at.asc())
            )
            stmt = apply_options_context(stmt)
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
        async with db() as session:
            stmt1 = (
                select(TracePoint)
                .where(
                    func.ST_Intersects(
                        TracePoint.point, func.ST_GeomFromText(geometry.wkt, 4326)
                    ),
                    Trace.visibility.in_(("identifiable", "trackable")),
                )
                .order_by(
                    TracePoint.trace_id.desc(),
                    TracePoint.track_idx.asc(),
                    TracePoint.captured_at.asc(),
                )
            )
            stmt1 = apply_options_context(stmt1)
            stmt2 = (
                select(TracePoint)
                .where(
                    func.ST_Intersects(
                        TracePoint.point, func.ST_GeomFromText(geometry.wkt, 4326)
                    ),
                    Trace.visibility.in_(("public", "private")),
                )
                .order_by(
                    TracePoint.point.asc(),
                )
            )
            stmt2 = apply_options_context(stmt2)
            stmt = stmt1.union_all(stmt2)
            # TODO: this may require a correction

            if legacy_offset is not None:
                stmt = stmt.offset(legacy_offset)
            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def resolve_coords(
        traces: Sequence[Trace],
        *,
        limit_per_trace: int,
        resolution: int | None = None,
        type: Type[int | float] = int,
    ) -> None:
        """
        Resolve coords for traces.
        """
        traces_: list[Trace] = []
        id_points_map: dict[int, list[Point]] = {}
        for trace in traces:
            if trace.coords is None:
                traces_.append(trace)
                id_points_map[trace.id] = trace.coords = []

        if not traces_:
            return

        async with db() as session:
            stmts = []

            for trace in traces_:
                stmt_ = (
                    select(
                        TracePoint.trace_id,
                        TracePoint.point,
                        func.row_number().over().label("row_number"),
                    )
                    .where(TracePoint.trace_id == trace.id)
                    .order_by(TracePoint.track_idx.asc(), TracePoint.captured_at.asc())
                )

                if trace.size > limit_per_trace:
                    indices = np.round(
                        np.linspace(1, trace.size, limit_per_trace)
                    ).astype(int)
                    subq = stmt_.subquery()
                    stmt_ = (
                        subq.select()
                        .where(subq.c.row_number.in_(indices))  #
                        .order_by(subq.c.row_number)
                    )

                stmts.append(stmt_)

            rows = (await session.execute(union_all(*stmts))).all()

        current_trace_id: int = 0
        current_points: list[Point] = []

        for trace_id, point, _ in rows:
            if current_trace_id != trace_id:
                current_trace_id = trace_id
                current_points = id_points_map[trace_id]
            current_points.append(point)

        for trace in traces_:
            if trace.size < 2:
                trace.coords.clear()
                continue

            array = lib.get_coordinates(
                np.asarray(trace.coords, dtype=object), False, False
            )
            if resolution:
                array = mercator(array, resolution, resolution)

            trace.coords = array.astype(type).flatten().tolist()
