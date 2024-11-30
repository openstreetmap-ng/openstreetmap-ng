import logging

import cython
import numpy as np
from fastapi import UploadFile
from shapely import lib

from app.db import db_commit
from app.format.gpx import FormatGPX
from app.lib.auth_context import auth_user
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.trace_file import TraceFile
from app.lib.xmltodict import XMLToDict
from app.limits import TRACE_FILE_UPLOAD_MAX_SIZE
from app.models.db.trace_ import Trace, TraceVisibility
from app.models.db.trace_segment import TraceSegment
from app.models.validating.trace_ import TraceValidating
from app.storage import TRACES_STORAGE


class TraceService:
    @staticmethod
    async def upload(
        file: UploadFile,
        *,
        description: str,
        tags: str,
        visibility: TraceVisibility,
    ) -> Trace:
        """
        Process upload of a trace file.

        Returns the created trace object.
        """
        file_size = file.size
        if file_size is None or file_size > TRACE_FILE_UPLOAD_MAX_SIZE:
            raise_for.input_too_big(file_size or -1)

        file_bytes = await file.read()
        segments: list[TraceSegment] = []

        # process multiple files in the archive
        try:
            for gpx_bytes in TraceFile.extract(file_bytes):
                tracks = XMLToDict.parse(gpx_bytes).get('gpx', {}).get('trk', [])
                track_num_start = (segments[-1].track_num + 1) if segments else 0
                segments.extend(FormatGPX.decode_tracks(tracks, track_num_start=track_num_start))
        except Exception as e:
            raise_for.bad_trace_file(str(e))

        size = lib.count_coordinates(np.asarray(tuple(segment.points for segment in segments), dtype=np.object_))
        logging.debug('Organized %d points into %d segments', size, len(segments))
        if size < 2:
            raise_for.bad_trace_file('not enough points')

        trace = Trace(
            **TraceValidating(
                user_id=auth_user(required=True).id,
                name=_get_file_name(file),
                description=description,
                visibility=visibility,
                size=size,
            ).__dict__
        )
        trace.tag_string = tags
        compressed_file, compressed_suffix = TraceFile.compress(file_bytes)
        trace.file_id = await TRACES_STORAGE.save(compressed_file, compressed_suffix)

        try:
            async with db_commit() as session:
                session.add(trace)
                await session.flush()

                trace_id = trace.id
                for segment in segments:
                    segment.trace_id = trace_id
                session.add_all(segments)

        except Exception:
            # clean up trace file on error
            await TRACES_STORAGE.delete(trace.file_id)
            raise

        return trace

    @staticmethod
    async def update(
        trace_id: int,
        *,
        name: str,
        description: str,
        tag_string: str,
        visibility: TraceVisibility,
    ) -> None:
        """
        Update a trace.
        """
        async with db_commit() as session:
            trace = await session.get(Trace, trace_id, with_for_update=True)

            if trace is None:
                raise_for.trace_not_found(trace_id)
            if trace.user_id != auth_user(required=True).id:
                raise_for.trace_access_denied(trace_id)

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
                raise_for.trace_not_found(trace_id)
            if trace.user_id != auth_user(required=True).id:
                raise_for.trace_access_denied(trace_id)

            await session.delete(trace)


@cython.cfunc
def _get_file_name(file: UploadFile) -> str:
    """
    Get the file name from the upload file.

    If not provided, use the current time as the file name.
    """
    filename = file.filename
    return filename if (filename is not None) else f'{utcnow().isoformat(timespec="seconds")}.gpx'
