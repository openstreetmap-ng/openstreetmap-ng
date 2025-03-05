from typing import Any

import cython
import numpy as np
from numpy.typing import NDArray
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable
from shapely import MultiLineString, MultiPoint, MultiPolygon, Polygon, STRtree, force_2d, get_parts, lib

from app.db import db2
from app.lib.auth_context import auth_user_scopes
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import polygon_to_h3
from app.lib.mercator import mercator
from app.lib.storage import TRACES_STORAGE
from app.lib.trace_file import TraceFile
from app.models.db.trace import Trace, TraceId, TraceVisibility, trace_is_visible_to
from app.models.db.user import UserId
from app.models.types import StorageKey


class TraceQuery:
    @staticmethod
    async def get_one_by_id(trace_id: TraceId) -> Trace:
        """
        Get a trace by id.
        Raises if the trace is not visible to the current user.
        """
        async with (
            db2() as conn,
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
        if not trace_is_visible_to(trace, *auth_user_scopes()):
            raise_for.trace_access_denied(trace_id)

        return trace

    @staticmethod
    async def get_one_data_by_id(trace_id: TraceId) -> bytes:
        """
        Get a trace data file by id.
        Raises if the trace is not visible to the current user.
        Returns the file bytes.
        """
        trace = await TraceQuery.get_one_by_id(trace_id)
        file_buffer = await TRACES_STORAGE.load(trace['file_id'])
        file_bytes = TraceFile.decompress_if_needed(file_buffer, trace['file_id'])
        return file_bytes

    @staticmethod
    async def count_by_user_id(user_id: UserId) -> int:
        """Count traces by user id."""
        query = SQL("""
            SELECT COUNT(*) FROM trace
            WHERE user_id = %s
        """)

        # If unauthenticated, count public traces
        user, scopes = auth_user_scopes()
        if user is None or user['id'] != user_id or 'read_gpx' not in scopes:
            query = SQL("{} AND visibility IN ('identifiable', 'public')").format(query)

        async with db2() as conn, await conn.execute(query, (user_id,)) as r:
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def find_many_recent(
        *,
        user_id: UserId | None = None,
        tag: str | None = None,
        after: TraceId | None = None,
        before: TraceId | None = None,
        limit: int,
    ) -> list[Trace]:
        """Find recent traces."""
        order_desc: cython.bint = (after is None) or (before is not None)
        conditions: list[Composable] = []
        params: list[Any] = []

        # If unauthenticated, find public traces
        user, scopes = auth_user_scopes()
        if user is None or user['id'] != user_id or 'read_gpx' not in scopes:
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

        query = SQL("""
            SELECT * FROM trace
            WHERE {conditions}
            ORDER BY id {order}
            LIMIT %s
        """).format(
            conditions=SQL(' AND ').join(conditions) if conditions else SQL('TRUE'),
            order=SQL('DESC' if order_desc else 'ASC'),
        )
        params.append(limit)

        # Always return in consistent order regardless of the query
        if not order_desc:
            query = SQL("""
                SELECT * FROM ({})
                ORDER BY id DESC
            """).format(query)

        async with db2() as conn, await conn.cursor(row_factory=dict_row).execute(query, params) as r:
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_many_by_geometry(
        geometry: Polygon | MultiPolygon,
        *,
        identifiable_trackable: cython.bint,
        limit: int,
        legacy_offset: int | None = None,
    ) -> list[Trace]:
        """Find traces by geometry. Returns traces with segments intersecting the provided geometry."""
        h3_cells = polygon_to_h3(geometry, max_resolution=11)
        # noinspection PyTypeChecker
        visibility: list[TraceVisibility] = (
            ['identifiable', 'trackable'] if identifiable_trackable else ['public', 'private']
        )
        conditions: list[Composable] = [SQL('h3_r11 && %s AND visibility = ANY(%s)')]
        params: list[Any] = [h3_cells, visibility]

        if legacy_offset is not None:
            offset_clause = SQL('OFFSET %s')
            params.append(legacy_offset)
        else:
            offset_clause = SQL('')

        query = SQL("""
            SELECT * FROM trace
            WHERE {conditions}
            ORDER BY id DESC
            {offset}
            LIMIT %s
        """).format(
            conditions=SQL(' AND ').join(conditions),
            offset=offset_clause,
        )
        params.append(limit)

        async with db2() as conn, await conn.cursor(row_factory=dict_row).execute(query, params) as r:
            traces: list[Trace] = await r.fetchall()  # type: ignore
        if not traces:
            return []

        tree = STRtree([geometry])

        for trace in traces:
            points: NDArray[np.object_]
            segment_indices: NDArray[np.integer]
            intersect_indices: NDArray[np.integer]

            points, segment_indices = get_parts(trace['segments'].geoms, return_index=True)  # type: ignore
            intersect_indices = tree.query(points, predicate='intersects')[0]
            split_indices = np.unique(segment_indices[intersect_indices], return_index=True)[1][1:]

            # Reconstruct segments to contain only intersecting points
            trace['segments'] = MultiLineString(np.split(points[intersect_indices], split_indices))

            if identifiable_trackable:
                # Reconstruct capture_times to match new segments
                # Public/private visibility discards capture_times
                capture_times = trace['capture_times']
                if capture_times is not None:
                    trace['capture_times'] = np.array(capture_times, np.object_)[intersect_indices].tolist()  # type: ignore

        if identifiable_trackable:
            return traces

        # For public/private, return a simplified representation
        segments = force_2d(MultiLineString([line for trace in traces for line in trace['segments'].geoms]))
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
            'capture_times': None,
            'created_at': now,
            'updated_at': now,
        }
        return [simplified]

    @staticmethod
    async def resolve_coords(
        traces: list[Trace],
        *,
        limit_per_trace: int,
        resolution: int | None,
    ) -> None:
        """Resolve coordinates for traces, with optional sampling and resolution adjustment."""
        if not traces:
            return

        trace_map = {trace['id']: trace for trace in traces}

        async with (
            db2() as conn,
            await conn.execute(
                """
                SELECT id, ST_Collect(point)
                FROM (
                    SELECT
                        id,
                        (dp).geom AS point,
                        (dp).path[1] AS index,
                        size
                    FROM trace
                    CROSS JOIN LATERAL ST_DumpPoints(ST_Force2D(segments)) AS dp
                    WHERE id = ANY(%s)
                )
                WHERE index % GREATEST(1, (size / %s)::int) = 0
                GROUP BY id
                """,
                (list(trace_map), limit_per_trace),
            ) as r,
        ):
            trace_id: TraceId
            geom: MultiPoint
            for trace_id, geom in await r.fetchall():
                coords = lib.get_coordinates(np.asarray(geom, dtype=np.object_), False, False)

                # Apply resolution transformation if needed
                if resolution is not None and len(coords) >= 2:
                    coords = mercator(coords, resolution, resolution).astype(np.uint)
                elif len(coords) < 2:
                    coords = np.empty((0,), dtype=np.uint)

                trace_map[trace_id]['coords'] = coords
