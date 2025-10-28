from typing import Any

import cython
import numpy as np
from numpy.typing import NDArray
from psycopg import IsolationLevel
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable
from psycopg.sql import Literal as PgLiteral
from shapely import (
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Polygon,
    get_coordinates,
    intersects_xy,
    prepare,
)

from app.db import db
from app.lib.auth_context import auth_scopes, auth_user
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import polygon_to_h3
from app.lib.mercator import mercator
from app.lib.storage import TRACE_STORAGE
from app.lib.trace_file import TraceFile
from app.models.db.trace import Trace, trace_is_visible
from app.models.types import StorageKey, TraceId, UserId
from app.queries.timescaledb_query import TimescaleDBQuery


class TraceQuery:
    @staticmethod
    async def get_one_by_id(trace_id: TraceId) -> Trace:
        """
        Get a trace by id.
        Raises if the trace is not visible to the current user.
        """
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM trace
                WHERE id = %s
                """,
                (trace_id,),
            ) as r,
        ):
            trace: Trace | None = await r.fetchone()  # type: ignore

        if trace is None:
            raise_for.trace_not_found(trace_id)
        if not trace_is_visible(trace):
            raise_for.trace_access_denied(trace_id)

        return trace

    @staticmethod
    async def find_by_ids(ids: list[TraceId]) -> list[Trace]:
        """Find traces by ids for report context."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM trace
                WHERE id = ANY(%s)
                """,
                (ids,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def get_one_data_by_id(trace_id: TraceId) -> bytes:
        """
        Get a trace data file by id.
        Raises if the trace is not visible to the current user.
        Returns the file bytes.
        """
        trace = await TraceQuery.get_one_by_id(trace_id)
        file_buffer = await TRACE_STORAGE.load(trace['file_id'])
        file_bytes = TraceFile.decompress_if_needed(file_buffer, trace['file_id'])
        return file_bytes

    @staticmethod
    async def count_by_user(user_id: UserId) -> int:
        """Count traces by user id."""
        query = SQL("""
            SELECT COUNT(*) FROM trace
            WHERE user_id = %s
        """)

        # If unauthenticated, count public traces
        user = auth_user()
        if user is None or user['id'] != user_id or 'read_gpx' not in auth_scopes():
            query = SQL("{} AND visibility IN ('identifiable', 'public')").format(query)

        async with db() as conn, await conn.execute(query, (user_id,)) as r:
            return (await r.fetchone())[0]  # type: ignore

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
        conditions: list[Composable] = []
        params: list[Any] = []

        # If unauthenticated, find public traces
        user = auth_user()
        if user is None or user['id'] != user_id or 'read_gpx' not in auth_scopes():
            conditions.append(SQL("visibility IN ('identifiable', 'public')"))

        if user_id is not None:
            conditions.append(SQL('user_id = %s'))
            params.append(user_id)

        if tag is not None:
            conditions.append(SQL('tags @> ARRAY[%s]'))
            params.append(tag)

        if before is not None:
            conditions.append(SQL('id < %s'))
            params.append(before)

        if after is not None:
            conditions.append(SQL('id > %s'))
            params.append(after)

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        query = SQL("""
            SELECT * FROM trace
            WHERE {conditions}
            ORDER BY id {order}
            {limit}
        """).format(
            conditions=SQL(' AND ').join(conditions) if conditions else SQL('TRUE'),
            order=SQL('DESC' if order_desc else 'ASC'),
            limit=limit_clause,
        )

        # Always return in consistent order regardless of the query
        if not order_desc:
            query = SQL("""
                SELECT * FROM ({})
                ORDER BY id DESC
            """).format(query)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_by_geom(
        geometry: Polygon | MultiPolygon,
        *,
        identifiable_trackable: cython.bint,
        limit: int,
        legacy_offset: int | None = None,
    ) -> list[Trace]:
        """Find traces by geometry. Returns traces with segments intersecting the provided geometry."""
        params: dict[str, Any] = {
            'h3_cells': polygon_to_h3(geometry, max_resolution=11),
            'visibility': (
                ['identifiable', 'trackable']
                if identifiable_trackable
                else ['public', 'private']
            ),
            'limit': limit,
        }

        if legacy_offset is not None:
            offset_clause = SQL('OFFSET %(legacy_offset)s')
            params['legacy_offset'] = legacy_offset
        else:
            offset_clause = SQL('')

        async with db(isolation_level=IsolationLevel.REPEATABLE_READ) as conn:
            query = SQL("""
                /*+ BitmapScan(trace trace_segments_idx) */
                SELECT * FROM ({query})
                {offset}
                LIMIT %(limit)s
            """).format(
                query=SQL(' UNION ALL ').join([
                    SQL("""(
                        SELECT * FROM trace
                        WHERE h3_points_to_cells_range(segments, 11) && %(h3_cells)s::h3index[]
                        AND visibility = ANY(%(visibility)s)
                        AND id BETWEEN {chunk_start} AND {chunk_end}
                        ORDER BY id DESC
                    )""").format(
                        chunk_start=PgLiteral(chunk_start),
                        chunk_end=PgLiteral(chunk_end),
                    )
                    for chunk_start, chunk_end in await TimescaleDBQuery.get_chunks_ranges(
                        'trace', conn
                    )
                ]),
                offset=offset_clause,
            )

            async with await conn.cursor(row_factory=dict_row).execute(
                query, params
            ) as r:
                traces: list[Trace] = await r.fetchall()  # type: ignore
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
            if not new_points.size:
                continue
            new_segment_indices = segment_indices[intersect_mask]
            filtered_traces.append(trace)

            split_indices = np.unique(new_segment_indices, return_index=True)[1][1:]
            segments = np.split(new_points, split_indices)
            trace['segments'] = MultiLineString(segments)

            if identifiable_trackable:
                # Reconstruct capture_times to match new segments
                # Public/private visibility discards elevations and capture_times
                elevations = trace['elevations']
                if elevations is not None:
                    elevations_arr = np.array(elevations, np.object_)
                    trace['elevations'] = elevations_arr[intersect_mask].tolist()

                capture_times = trace['capture_times']
                if capture_times is not None:
                    capture_times_arr = np.array(capture_times, np.object_)
                    trace['capture_times'] = capture_times_arr[intersect_mask].tolist()

        traces = filtered_traces
        if not traces or identifiable_trackable:
            return traces

        # For public/private, return a simplified representation
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
    ) -> None:
        """Resolve coordinates for traces, with optional sampling and resolution adjustment."""
        if not traces:
            return

        trace_map = {trace['id']: trace for trace in traces}
        params: list[Any] = [list(trace_map)]

        if limit_per_trace is not None:
            where_clause = SQL('WHERE index %% GREATEST(1, (size / %s)::int) = 0')
            params.append(limit_per_trace)
        else:
            where_clause = SQL('')

        query = SQL("""
            SELECT id, ST_Collect(point)
            FROM (
                SELECT
                    id,
                    (dp).geom AS point,
                    (ROW_NUMBER() OVER (PARTITION BY id ORDER BY (dp).path) - 1) AS index,
                    size
                FROM trace
                CROSS JOIN LATERAL ST_DumpPoints(ST_Force2D(segments)) AS dp
                WHERE id = ANY(%s)
            )
            {where}
            GROUP BY id
            """).format(where=where_clause)

        async with (
            db() as conn,
            await conn.execute(query, params) as r,
        ):
            trace_id: TraceId
            geom: MultiPoint

            for trace_id, geom in await r.fetchall():
                coords = get_coordinates(geom)

                if resolution is not None:
                    # Optionally scale coordinates to the given resolution
                    coords = (
                        mercator(coords, resolution, resolution).astype(np.uint)
                        if len(coords) >= 2
                        else np.empty((0,), dtype=np.uint)
                    )

                trace_map[trace_id]['coords'] = coords
