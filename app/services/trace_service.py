from collections.abc import Sequence
from datetime import timedelta
from itertools import pairwise

import anyio
import cython
from anyio import to_thread
from fastapi import UploadFile

from app.db import db_autocommit
from app.format06 import Format06
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.trace_file import TraceFile
from app.lib.trace_image import TraceImage
from app.lib.xmltodict import XMLToDict
from app.limits import TRACE_FILE_UPLOAD_MAX_SIZE
from app.models.db.trace_ import Trace
from app.models.db.trace_point import TracePoint
from app.models.trace_visibility import TraceVisibility
from app.models.validating.trace_ import TraceValidating
from app.storage import TRACES_STORAGE


@cython.cfunc
def _sort_and_deduplicate(points: Sequence[TracePoint]) -> list[TracePoint]:
    """
    Sort and deduplicates the points.

    The points are sorted by captured_at, then by longitude, then by latitude.
    """

    max_pos_diff = 1e-7  # different up to 7 decimal places
    max_date_diff = timedelta(seconds=1)

    sorted_points = sorted(points, key=lambda p: (p.captured_at, p.point.x, p.point.y))
    deduped_points = [sorted_points[0]]

    for prev, point in pairwise(sorted_points):
        if (
            abs(point.point.x - prev.point.x) < max_pos_diff
            and abs(point.point.y - prev.point.y) < max_pos_diff
            and point.captured_at - prev.captured_at < max_date_diff  # check date last, slowest to compute
        ):
            continue
        deduped_points.append(point)

    return deduped_points


class TraceService:
    @staticmethod
    async def upload(file: UploadFile, description: str, tags: str, visibility: TraceVisibility) -> Trace:
        """
        Process upload of a trace file.

        Returns the created trace object.
        """

        file_size_len = len(file.size)
        if file_size_len > TRACE_FILE_UPLOAD_MAX_SIZE:
            raise_for().input_too_big(file_size_len)

        file_bytes = await to_thread.run_sync(file.file.read)
        points: list[TracePoint] = []

        # process multiple files in the archive
        try:
            for gpx_bytes in TraceFile.extract(file_bytes):
                gpx = gpx_bytes.decode()
                tracks = XMLToDict.parse(gpx).get('gpx', {}).get('trk', [])

                track_idx_last = points[-1].track_idx if points else -1
                points.extend(Format06.decode_tracks(tracks, track_idx_start=track_idx_last))
        except Exception as e:
            raise_for().bad_trace_file(str(e))

        points = _sort_and_deduplicate(points)

        # require two distinct points for sane bounding box and icon
        if len(points) < 2:
            raise_for().bad_trace_file('not enough points')

        trace = Trace(
            **TraceValidating(
                user_id=auth_user().id,
                name=file.filename,
                description=description,
                visibility=visibility,
                size=len(points),
                start_point=points[0].point,
                tags=(),  # set with .tag_string
            ).to_orm_dict()
        )

        trace.points = points
        trace.tag_string = tags

        image, icon = await TraceImage.generate_async(points)
        compressed_file, compressed_suffix = TraceFile.zstd_compress(file_bytes)

        async def save_file() -> None:
            trace.file_id = await TRACES_STORAGE.save(compressed_file, compressed_suffix)

        async def save_image() -> None:
            trace.image_id = await TRACES_STORAGE.save(image, TraceImage.image_suffix)

        async def save_icon() -> None:
            trace.icon_id = await TRACES_STORAGE.save(icon, TraceImage.icon_suffix)

        # save the files after the validation
        async with anyio.create_task_group() as tg:
            tg.start_soon(save_file)
            tg.start_soon(save_image)
            tg.start_soon(save_icon)

        async with db_autocommit() as session:
            session.add(trace)

        return trace

    @staticmethod
    async def update(trace_id: int, new_trace: Trace) -> None:
        """
        Update a trace.
        """

        async with db_autocommit() as session:
            trace = await session.get(Trace, trace_id, with_for_update=True)

            if trace is None:
                raise_for().trace_not_found(trace_id)
            if trace.user_id != auth_user().id:
                raise_for().trace_access_denied(trace_id)

            trace.name = new_trace.name
            trace.description = new_trace.description
            trace.visibility = new_trace.visibility
            trace.tags = new_trace.tags

    @staticmethod
    async def delete(trace_id: int) -> None:
        """
        Delete a trace.
        """

        async with db_autocommit() as session:
            trace = await session.get(Trace, trace_id, with_for_update=True)

            if trace is None:
                raise_for().trace_not_found(trace_id)
            if trace.user_id != auth_user().id:
                raise_for().trace_access_denied(trace_id)

            await session.delete(trace)
