from collections import Counter
from collections.abc import Collection, Sequence

import cython
import numpy as np
from shapely import MultiPoint, STRtree, from_wkb, get_parts, lib, multipoints
from shapely.geometry.base import BaseGeometry
from sqlalchemy import func, literal_column, select, text, union_all
from sqlalchemy.sql.selectable import Select

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
                .order_by(
                    TraceSegment.track_num.asc(),
                    TraceSegment.segment_num.asc(),
                )
            )
            stmt = apply_options_context(stmt)
            return (await session.scalars(stmt)).all()

    @staticmethod
    async def find_many_by_geometry(
        geometry: BaseGeometry,
        *,
        identifiable_trackable: bool,
        limit: int | None,
        legacy_offset: int | None = None,
    ) -> Sequence[TraceSegment]:
        """
        Find trace segments by geometry.

        Returns modified segments, containing only points within the geometry.
        """
        visibility = ('identifiable', 'trackable') if identifiable_trackable else ('public', 'private')

        async with db() as session:
            stmt = (
                select(TraceSegment)
                .join(TraceSegment.trace)
                .where(
                    func.ST_Intersects(TraceSegment.points, func.ST_GeomFromText(geometry.wkt, 4326)),
                    Trace.visibility.in_(visibility),
                )
                .order_by(
                    TraceSegment.trace_id.desc(),
                    TraceSegment.track_num.asc(),
                    TraceSegment.segment_num.asc(),
                )
            )
            stmt = apply_options_context(stmt)
            if legacy_offset is not None:
                stmt = stmt.offset(legacy_offset)
            if limit is not None:
                stmt = stmt.limit(limit)
            segments = (await session.scalars(stmt)).all()

        if not segments:
            return ()

        # extract points and check for intersections
        segments_points = tuple(segment.points for segment in segments)
        segments_parts_ = get_parts(segments_points, return_index=True)
        segments_parts = segments_parts_[0]
        segments_indices = segments_parts_[1]
        tree = STRtree((geometry,))
        intersect_indices = tree.query(segments_parts, predicate='intersects')[0]
        if not intersect_indices.size:
            return ()

        # filter non-intersecting points
        segments_parts = segments_parts[intersect_indices]
        segments_indices = segments_indices[intersect_indices]
        split_indices = np.unique(segments_indices, return_index=True)[1][1:]
        new_parts = np.split(segments_parts, split_indices)
        new_parts_flat = np.concatenate(new_parts)

        if identifiable_trackable:
            # reconstruct multipoints
            split_indices_ex = np.empty(len(split_indices) + 2, dtype=split_indices.dtype)
            split_indices_ex[0] = 0
            split_indices_ex[1:-1] = split_indices
            split_indices_ex[-1] = len(segments_parts)
            new_parts_sizes = split_indices_ex[1:] - split_indices_ex[:-1]
            new_parts_max_size: int = new_parts_sizes.max()
            new_parts_fixed = np.empty((len(new_parts), new_parts_max_size), dtype=object)
            mask = np.arange(new_parts_max_size) < new_parts_sizes[:, None]
            new_parts_fixed[mask] = new_parts_flat
            new_points_list: Sequence[MultiPoint] = multipoints(new_parts_fixed)  # pyright: ignore[reportAssignmentType]

            # assign filtered multipoints and return
            for segment, points in zip(segments, new_points_list, strict=True):
                segment.points = points

            # filter extra attributes
            data_flat = np.empty(segments_parts_[0].size, dtype=object)
            data_lens = Counter(segments_parts_[1]).values()
            dirty: cython.char = False
            for attr_name in ('capture_times', 'elevations'):
                if dirty:
                    data_flat.fill(None)
                    dirty = False
                i: int = 0
                for segment, data_len in zip(segments, data_lens, strict=True):
                    data = getattr(segment, attr_name)
                    if data:
                        data_flat[i : i + data_len] = data
                        dirty = True
                    i += data_len
                if dirty:
                    new_data = np.split(data_flat[intersect_indices], split_indices)
                    for segment, data in zip(segments, new_data, strict=True):
                        setattr(segment, attr_name, data.tolist())

            return segments
        else:
            # reconstruct dummy multipoint
            new_points: MultiPoint = multipoints(new_parts_flat)  # pyright: ignore[reportAssignmentType]
            return (
                TraceSegment(
                    track_num=0,
                    segment_num=0,
                    points=new_points,
                    capture_times=None,
                    elevations=None,
                ),
            )

    @staticmethod
    async def resolve_coords(
        traces: Collection[Trace],
        *,
        limit_per_trace: int,
        resolution: int | None,
    ) -> None:
        """
        Resolve coords for traces.
        """
        trace_id_map: dict[int, Trace] = {trace.id: trace for trace in traces}
        if not trace_id_map:
            return

        async with db() as session:
            stmts: list[Select] = [None] * len(traces)  # pyright: ignore[reportAssignmentType]
            i: cython.int
            for i, trace in enumerate(traces):
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
                        .subquery()
                    )

                stmt_ = select(text(str(trace.id)), subq.c.geom).select_from(subq)
                stmts[i] = stmt_

            rows = (await session.execute(union_all(*stmts))).all()

        for trace_id, wkb in rows:
            trace = trace_id_map[trace_id]
            geom = from_wkb(wkb)
            coords = lib.get_coordinates(np.asarray(geom, dtype=object), False, False)
            if resolution is not None:
                if len(coords) < 2:
                    trace.coords = np.empty((0,), dtype=np.uint)
                    continue
                coords = mercator(coords, resolution, resolution).astype(np.uint)
            trace.coords = coords
