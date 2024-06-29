from collections.abc import Sequence

import numpy as np
from shapely import from_wkb, lib
from shapely.ops import BaseGeometry
from sqlalchemy import func, literal_column, select, text, union_all

from app.db import db
from app.lib.mercator import mercator
from app.lib.options_context import apply_options_context
from app.models.db.trace_ import Trace
from app.models.db.trace_segment import TraceSegment


# TODO: limit offset for safety
class TraceSegmentQuery:
    @staticmethod
    async def get_many_by_trace_id(trace_id: int) -> Sequence[TraceSegment]:
        """
        Get trace segments by trace id.
        """
        async with db() as session:
            stmt = (
                select(TraceSegment)
                .where(TraceSegment.trace_id == trace_id)
                .order_by(TraceSegment.track_num.asc(), TraceSegment.segment_num.asc())
            )
            stmt = apply_options_context(stmt)
            return (await session.scalars(stmt)).all()

    @staticmethod
    async def find_many_by_geometry(
        geometry: BaseGeometry,
        *,
        limit: int | None,
        legacy_offset: int | None = None,
    ) -> Sequence[TraceSegment]:
        """
        Find trace points by geometry.
        """
        async with db() as session:
            stmt1 = (
                select(TraceSegment)
                .where(
                    func.ST_Intersects(TraceSegment.point, func.ST_GeomFromText(geometry.wkt, 4326)),
                    Trace.visibility.in_(('identifiable', 'trackable')),
                )
                .order_by(
                    TraceSegment.trace_id.desc(),
                    TraceSegment.track_idx.asc(),
                    TraceSegment.captured_at.asc(),
                )
            )
            stmt1 = apply_options_context(stmt1)
            stmt2 = (
                select(TraceSegment)
                .where(
                    func.ST_Intersects(TraceSegment.point, func.ST_GeomFromText(geometry.wkt, 4326)),
                    Trace.visibility.in_(('public', 'private')),
                )
                .order_by(
                    TraceSegment.point.asc(),
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
        resolution: int | None,
    ) -> None:
        """
        Resolve coords for traces.
        """
        id_trace_map: dict[int, Trace] = {trace.id: trace for trace in traces if trace.coords is None}
        if not id_trace_map:
            return

        async with db() as session:
            stmts = []

            for trace in id_trace_map.values():
                subq = (
                    select(TraceSegment.points)
                    .where(TraceSegment.trace_id == trace.id)
                    .order_by(TraceSegment.track_num.asc(), TraceSegment.segment_num.asc())
                    .subquery()
                )
                subq = (
                    select(func.ST_Collect(subq.c.points).label('geom'))  #
                    .select_from(subq)
                    .subquery()
                )

                if trace.size > limit_per_trace:
                    indices = np.round(np.linspace(1, trace.size, limit_per_trace)).astype(int)
                    subq = (
                        select(func.ST_DumpPoints(subq.c.geom).label('dp'))  #
                        .select_from(subq)
                        .subquery()
                    )
                    subq = (
                        select(literal_column('(dp).geom').label('geom'))  #
                        .select_from(subq)
                        .subquery()
                    )
                    subq = (
                        select(
                            subq.c.geom,
                            func.row_number().over().label('row_number'),
                        )
                        .select_from(subq)
                        .subquery()
                    )
                    subq = (
                        select(func.ST_Collect(subq.c.geom).label('geom'))  #
                        .select_from(subq)
                        .where(subq.c.row_number.in_(text(','.join(map(str, indices)))))
                    )

                stmt_ = select(text(str(trace.id)), subq.c.geom).select_from(subq)
                stmts.append(stmt_)

            rows = (await session.execute(union_all(*stmts))).all()

        for trace_id, wkb in rows:
            trace = id_trace_map[trace_id]
            geom = from_wkb(wkb)
            coords: np.ndarray = lib.get_coordinates(np.asarray(geom, dtype=object), False, False)
            if len(coords) < 2:
                trace.coords = []
                continue
            if resolution is not None:
                coords = mercator(coords, resolution, resolution).astype(int)
            trace.coords = coords.flatten().tolist()
