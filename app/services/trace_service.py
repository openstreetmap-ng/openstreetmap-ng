from collections.abc import Sequence

import cython
from anyio import to_thread
from fastapi import UploadFile

from app.db import db_commit
from app.format06 import Format06
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.trace_file import TraceFile
from app.lib.xmltodict import XMLToDict
from app.limits import TRACE_FILE_UPLOAD_MAX_SIZE
from app.models.db.trace_ import Trace
from app.models.db.trace_point import TracePoint
from app.models.trace_visibility import TraceVisibility
from app.storage import TRACES_STORAGE
from app.validators.trace_ import TraceValidating


class TraceService:
    @staticmethod
    async def upload(file: UploadFile, *, description: str, tags: str, visibility: TraceVisibility) -> Trace:
        """
        Process upload of a trace file.

        Returns the created trace object.
        """
        if file.size > TRACE_FILE_UPLOAD_MAX_SIZE:
            raise_for().input_too_big(file.size)

        file_bytes = await to_thread.run_sync(file.file.read)
        points: list[TracePoint] = []

        # process multiple files in the archive
        try:
            for gpx_bytes in TraceFile.extract(file_bytes):
                tracks = XMLToDict.parse(gpx_bytes).get('gpx', {}).get('trk', [])
                track_idx_start = (points[-1].track_idx + 1) if points else 0
                points.extend(Format06.decode_tracks(tracks, track_idx_start=track_idx_start))
        except Exception as e:
            raise_for().bad_trace_file(str(e))

        points = _sort_and_deduplicate(points)

        # require two distinct points for sane bounding box and icon
        if len(points) < 2:
            raise_for().bad_trace_file('not enough points')

        trace = Trace(
            **dict(
                TraceValidating(
                    user_id=auth_user().id,
                    name=file.filename,
                    description=description,
                    visibility=visibility,
                    size=len(points),
                    start_point=points[0].point,
                )
            )
        )

        trace.tag_string = tags

        compressed_file, compressed_suffix = TraceFile.compress(file_bytes)
        trace.file_id = await TRACES_STORAGE.save(compressed_file, compressed_suffix)

        try:
            async with db_commit() as session:
                session.add(trace)
                await session.flush()

                for point in points:
                    point.trace_id = trace.id
                    session.add(point)

        except Exception:
            # clean up trace file on error
            await TRACES_STORAGE.delete(trace.file_id)
            raise

        return trace

    @staticmethod
    async def update(
        trace_id: int, *, name: str, description: str, tag_string: str, visibility: TraceVisibility
    ) -> None:
        """
        Update a trace.
        """
        async with db_commit() as session:
            trace = await session.get(Trace, trace_id, with_for_update=True)

            if trace is None:
                raise_for().trace_not_found(trace_id)
            if trace.user_id != auth_user().id:
                raise_for().trace_access_denied(trace_id)

            trace.name = name
            trace.description = description
            trace.tag_string = tag_string
            trace.visibility = visibility

    @staticmethod
    async def delete(trace_id: int) -> None:
        """
        Delete a trace.
        """
        async with db_commit() as session:
            trace = await session.get(Trace, trace_id, with_for_update=True)

            if trace is None:
                raise_for().trace_not_found(trace_id)
            if trace.user_id != auth_user().id:
                raise_for().trace_access_denied(trace_id)

            await session.delete(trace)


@cython.cfunc
def _sort_and_deduplicate(points: Sequence[TracePoint]) -> list[TracePoint]:
    """
    Sort and deduplicates the points.
    """
    sorted_points = sorted(points, key=_point_sort_key)
    result = []
    prev_timestamp: cython.double = -1

    # not checking for track_idx - not worth the extra complexity
    # may lead to invalid deduplication in some edge cases

    for point in sorted_points:
        point_timestamp: cython.double = point.captured_at.timestamp()
        if point_timestamp - prev_timestamp < 1:
            continue

        result.append(point)
        prev_timestamp = point_timestamp

    return result


@cython.cfunc
def _point_sort_key(p: TracePoint) -> tuple:
    return p.track_idx, p.captured_at
