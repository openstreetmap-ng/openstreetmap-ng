import logging

import numpy as np
from anyio import to_thread
from fastapi import UploadFile
from shapely import lib

from app.db import db_commit
from app.format.gpx import FormatGPX
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.trace_file import TraceFile
from app.lib.xmltodict import XMLToDict
from app.limits import TRACE_FILE_UPLOAD_MAX_SIZE
from app.models.db.trace_ import Trace
from app.models.db.trace_segment import TraceSegment
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
        segments: list[TraceSegment] = []

        # process multiple files in the archive
        try:
            for gpx_bytes in TraceFile.extract(file_bytes):
                tracks = XMLToDict.parse(gpx_bytes).get('gpx', {}).get('trk', [])
                track_num_start = (segments[-1].track_num + 1) if segments else 0
                segments.extend(FormatGPX.decode_tracks(tracks, track_num_start=track_num_start))
        except Exception as e:
            raise_for().bad_trace_file(str(e))
        if not segments:
            raise_for().bad_trace_file('not enough points')

        size = sum(
            len(lib.get_coordinates(np.asarray(segment.points, dtype=object), False, False))  #
            for segment in segments
        )
        logging.debug('Organized %d points into %d segments', size, len(segments))

        trace = Trace(
            **dict(
                TraceValidating(
                    user_id=auth_user().id,
                    name=file.filename,
                    description=description,
                    visibility=visibility,
                    size=size,
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
