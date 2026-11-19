from string.templatelib import Template

import cython
import numpy as np
from numpy.typing import NDArray
from psycopg import IsolationLevel
from psycopg.sql import SQL
from shapely import (
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Polygon,
    get_coordinates,
    intersects_xy,
    prepare,
)

from app.db import (
    db,
    db_count,
    db_fetchall,
    db_fetchone,
    db_fetchrows,
    t_and,
    t_order,
)
from app.exceptions.context import raise_for
from app.lib.auth.context import auth_scopes, auth_user
from app.lib.geo.h3 import polygon_to_h3
from app.lib.geo.mercator import mercator
from app.lib.io.trace_file import TraceFile
from app.lib.storage import TRACE_STORAGE
from app.lib.time.date_utils import utcnow
from app.models.db.trace import Trace, trace_is_visible
from app.models.types import StorageKey, TraceId, UserId
from app.queries.timescaledb_query import TimescaleDBQuery

_UNION_ALL = SQL(' UNION ALL ')


class TraceQuery:
    @staticmethod
    async def get_by_id(trace_id: TraceId) -> Trace:
        """
        Get a trace by id.
        Raises if the trace is not visible to the current user.
        """
        trace = await db_fetchone(
            Trace,
            t"""
                SELECT * FROM trace
                WHERE id = {trace_id}
            """,
        )

        if trace is None:
            raise_for.trace_not_found(trace_id)
        if not trace_is_visible(trace):
            raise_for.trace_access_denied(trace_id)

        return trace

    @staticmethod
    async def find_by_ids(ids: list[TraceId]) -> list[Trace]:
        """Find traces by ids for report context."""
        return await db_fetchall(
            Trace,
            t"""
                SELECT * FROM trace
                WHERE id = ANY({ids})
            """,
        )

    @staticmethod
    async def get_one_data_by_id(trace_id: TraceId) -> bytes:
        """
        Get a trace data file by id.
        Raises if the trace is not visible to the current user.
        Returns the file bytes.
        """
        trace = await TraceQuery.get_by_id(trace_id)
        file_buffer = await TRACE_STORAGE.load(trace['file_id'])
        file_bytes = TraceFile.decompress_if_needed(file_buffer, trace['file_id'])
        return file_bytes

    @staticmethod
    async def count_by_user(user_id: UserId) -> int:
        """Count traces by user id."""
        # If unauthenticated, count public traces only
        user = auth_user()
        visibility_filter = (
            t"AND visibility IN ('identifiable', 'public')"
            if user is None or user['id'] != user_id or 'read_gpx' not in auth_scopes()
            else t''
        )

        return await db_count(
            'trace',
            where=t'user_id = {user_id} {visibility_filter:q}',
        )

    @staticmethod
    async def find_recent(
        *,
        user_id: UserId | None = None,
        tag: str | None = None,
        after: TraceId | None = None,
        before: TraceId | None = None,
        limit: int | None,
    ) -> list[Trace]:
        """Find recent traces."""
        order_desc: cython.bint = (after is None) or (before is not None)

        # If unauthenticated, find public traces
        user = auth_user()
        visibility_cond = (
            t"visibility IN ('identifiable', 'public')"
            if user is None or user['id'] != user_id or 'read_gpx' not in auth_scopes()
            else None
        )

        where = t_and(
            visibility_cond,
            t'user_id = {user_id}' if user_id is not None else None,
            t'tags @> ARRAY[{tag}]' if tag is not None else None,
            t'id < {before}' if before is not None else None,
            t'id > {after}' if after is not None else None,
        )
        order = t_order('desc' if order_desc else 'asc')

        # LIMIT must apply to inner ordering before optional subquery sort-flip,
        # so it's inlined rather than passed via db_fetchall's limit kwarg.
        limit_clause: Template = t'LIMIT {limit}' if limit is not None else t''
        query = t"""
            SELECT * FROM trace
            WHERE {where:q}
            ORDER BY id {order:q}
            {limit_clause:q}
        """

        # Always return in consistent order regardless of the query
        if not order_desc:
            query = t"""
                SELECT * FROM ({query:q})
                ORDER BY id DESC
            """

        return await db_fetchall(Trace, query)

    @staticmethod
    async def find_by_geom(
        geometry: Polygon | MultiPolygon,
        *,
        identifiable_trackable: cython.bint = False,
        visibility: list[str] | None = None,
        limit: int,
        legacy_offset: int | None = None,
        preserve_trace_details: bool | None = None,
    ) -> list[Trace]:
        """Find traces by geometry. Returns traces with segments intersecting the provided geometry."""
        h3_cells = polygon_to_h3(geometry, max_resolution=11)
        if visibility is None:
            visibility = (
                ['identifiable', 'trackable']
                if identifiable_trackable
                else ['public', 'private']
            )
        if preserve_trace_details is None:
            preserve_trace_details = identifiable_trackable

        async with db(isolation_level=IsolationLevel.REPEATABLE_READ) as conn:
            chunks = await TimescaleDBQuery.get_chunks_ranges('trace', conn)
            unions = _UNION_ALL.join([
                t"""(
                    SELECT * FROM trace
                    WHERE h3_points_to_cells_range(segments, 11) && {h3_cells}::h3index[]
                    AND visibility = ANY({visibility})
                    AND id BETWEEN {chunk_start} AND {chunk_end}
                    ORDER BY id DESC
                )"""
                for chunk_start, chunk_end in chunks
            ])

            traces = await db_fetchall(
                Trace,
                t"""
                    /*+ BitmapScan(trace trace_segments_idx) */
                    {unions:q}
                """,
                limit=limit,
                offset=legacy_offset,
                conn=conn,
            )
            if not traces:
                return []

        prepare(geometry)
        filtered_traces: list[Trace] = []

        points: NDArray[np.object_]
        segment_indices: NDArray[np.integer]

        for trace in traces:
            points, segment_indices = get_coordinates(
                trace['segments'].geoms,  # type: ignore
                return_index=True,
            )

            # Reconstruct segments to contain only intersecting points
            intersect_mask = intersects_xy(geometry, points)
            new_points = points[intersect_mask]
            if len(new_points) == 0:
                continue
            new_segment_indices = segment_indices[intersect_mask]
            filtered_traces.append(trace)

            split_indices = np.unique(new_segment_indices, return_index=True)[1][1:]
            segments = np.split(new_points, split_indices)
            trace['segments'] = MultiLineString(segments)

            if preserve_trace_details:
                # Reconstruct capture_times to match new segments
                # Simplified visibility groups discard elevations and capture_times.
                elevations = trace['elevations']
                if elevations is not None:
                    elevations_arr = np.array(elevations, np.object_)
                    trace['elevations'] = elevations_arr[intersect_mask].tolist()

                capture_times = trace['capture_times']
                if capture_times is not None:
                    capture_times_arr = np.array(capture_times, np.object_)
                    trace['capture_times'] = capture_times_arr[intersect_mask].tolist()

        traces = filtered_traces
        if not traces or preserve_trace_details:
            return traces

        # For anonymized display surfaces, return a simplified representation.
        segments = MultiLineString([
            line  #
            for trace in traces
            for line in trace['segments'].geoms
        ])
        now = utcnow()
        simplified: Trace = {
            'id': TraceId(0),
            'user_id': UserId(0),
            'name': '',
            'description': '',
            'tags': [],
            'visibility': 'private',
            'file_id': StorageKey(''),
            'size': 0,
            'segments': segments,
            'elevations': None,
            'capture_times': None,
            'created_at': now,
            'updated_at': now,
        }
        return [simplified]

    @staticmethod
    async def resolve_coords(
        traces: list[Trace],
        *,
        limit_per_trace: int | None = None,
        resolution: int | None,
    ):
        """Resolve coordinates for traces, with optional sampling and resolution adjustment."""
        if not traces:
            return

        trace_map = {trace['id']: trace for trace in traces}
        trace_ids = list(trace_map)

        where_clause = (
            t'WHERE index % GREATEST(1, (size / {limit_per_trace})::int) = 0'
            if limit_per_trace is not None
            else t''
        )

        rows = await db_fetchrows(t"""
            SELECT id, ST_Collect(point)
            FROM (
                SELECT
                    id,
                    (dp).geom AS point,
                    (ROW_NUMBER() OVER (PARTITION BY id ORDER BY (dp).path) - 1) AS index,
                    size
                FROM trace
                CROSS JOIN LATERAL ST_DumpPoints(ST_Force2D(segments)) AS dp
                WHERE id = ANY({trace_ids})
            )
            {where_clause:q}
            GROUP BY id
        """)
        trace_id: TraceId
        geom: MultiPoint

        for trace_id, geom in rows:
            coords = get_coordinates(geom)

            if resolution is not None:
                # Optionally scale coordinates to the given resolution
                coords = (
                    mercator(coords, resolution, resolution).astype(np.uint)
                    if len(coords) >= 2
                    else np.empty((0,), dtype=np.uint)
                )

            trace_map[trace_id]['coords'] = coords
