import logging

import cython
from fastapi import UploadFile
from asyncio import create_task, sleep

from app.config import TRACE_FILE_UPLOAD_MAX_SIZE
from app.db import db
from app.format.gpx import FormatGPX
from app.lib.auth_context import auth_user
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.storage import TRACE_STORAGE
from app.lib.trace_file import TraceFile
from app.lib.xmltodict import XMLToDict
from app.models.db.trace import (
    TraceInit,
    TraceInitValidator,
    TraceMetaInit,
    TraceMetaInitValidator,
    TraceVisibility,
    trace_tags_from_str,
)
from app.models.types import StorageKey, TraceId


class TraceService:
    @staticmethod
    async def upload(
        file: UploadFile,
        *,
        description: str,
        tags: str,
        visibility: TraceVisibility,
    ) -> TraceId:
        """Process upload of a trace file. Returns the created trace id."""
        file_size = file.size
        if file_size is None or file_size > TRACE_FILE_UPLOAD_MAX_SIZE:
            raise_for.input_too_big(file_size or -1)
        file_bytes = await file.read()

        try:
            tracks: list[dict] = []
            for gpx_bytes in TraceFile.extract(file_bytes):
                new_tracks = XMLToDict.parse(gpx_bytes).get(
                    'gpx', {}).get('trk', [])  # type: ignore
                tracks.extend(new_tracks)
        except Exception as e:
            raise_for.bad_trace_file(str(e))

        decoded = FormatGPX.decode_tracks(tracks)
        logging.debug('Organized %d points into %d segments',
                      decoded.size, len(decoded.segments.geoms))

        trace_init: TraceInit = {
            'user_id': auth_user(required=True)['id'],
            'name': _get_file_name(file),
            'description': description,
            'tags': trace_tags_from_str(tags),
            'visibility': visibility,
            'file_id': StorageKey(''),
            'size': decoded.size,
            'segments': decoded.segments,
            'capture_times': decoded.capture_times,
        }
        trace_init = TraceInitValidator.validate_python(trace_init)

        # Save the compressed file after validation to avoid unnecessary work
        result = await TraceFile.precompress(file_bytes)
        trace_init['file_id'] = await TRACE_STORAGE.save(result.data, result.suffix, result.metadata)
        logging.debug('Saved compressed trace file %r', trace_init['file_id'])

        try:
            # Insert into database
            async with (
                db(True) as conn,
                await conn.execute(
                    """
                    INSERT INTO trace (
                        user_id, name, description, tags, visibility,
                        file_id, size, segments, capture_times
                    ) VALUES (
                        %(user_id)s, %(name)s, %(description)s, %(tags)s, %(visibility)s,
                        %(file_id)s, %(size)s, %(segments)s, %(capture_times)s
                    )
                    RETURNING id
                    """,
                    trace_init,
                ) as r,
            ):
                trace_id = (await r.fetchone())[0]  # type: ignore

                # Create taks for heavy compression
                create_task(TraceService._compress(
                    trace_id, trace_init['file_id'], file_bytes))

                return trace_id

        except Exception:
            # Clean up trace file on error
            await TRACE_STORAGE.delete(trace_init['file_id'])
            raise

    @staticmethod
    async def _compress(trace_id: TraceId,  file_id: str, file_bytes: bytes):
        # compress
        new_file_id = None
        try:
            result = await TraceFile.compress(file_bytes)
            new_file_id = await TRACE_STORAGE.save(result.data, result.suffix, result.metadata)
            # upload to database
            async with (
                db(True) as conn,
                await conn.execute(
                    """
                    UPDATE trace
                    SET file_id = %(file_id)s
                    WHERE id = %(trace_id)s
                    """,
                    {"file_id": new_file_id, "trace_id": trace_id},
                )
            ):
                # after uplpading, delete previous file
                await TRACE_STORAGE.delete(StorageKey(file_id))
        except Exception as e:
            if new_file_id:
                # Clean up trace file on error
                await TRACE_STORAGE.delete(new_file_id)
                logging.error("Error updating trace database. id: %d", trace_id, exc_info=True)
            else:
                logging.error("Unexpected error while compressing trace. id: %d", trace_id, exc_info=True)


    @staticmethod
    async def update(
        trace_id: TraceId,
        *,
        name: str,
        description: str,
        tags: list[str],
        visibility: TraceVisibility,
    ) -> None:
        """Update a trace."""
        user_id = auth_user(required=True)['id']

        meta_init: TraceMetaInit = {
            'name': name,
            'description': description,
            'tags': tags,
            'visibility': visibility,
        }
        meta_init = TraceMetaInitValidator.validate_python(meta_init)

        async with db(True) as conn:
            result = await conn.execute(
                """
                UPDATE trace
                SET
                    name = %(name)s,
                    description = %(description)s,
                    tags = %(tags)s,
                    visibility = %(visibility)s,
                    updated_at = DEFAULT
                WHERE id = %(trace_id)s AND user_id = %(user_id)s
                """,
                {
                    **meta_init,
                    'trace_id': trace_id,
                    'user_id': user_id,
                },
            )

            if not result.rowcount:
                async with await conn.execute(
                    """
                    SELECT 1 FROM trace
                    WHERE id = %s
                    """,
                    (trace_id,),
                ) as r:
                    if await r.fetchone() is None:
                        raise_for.trace_not_found(trace_id)
                    else:
                        raise_for.trace_access_denied(trace_id)

    @staticmethod
    async def delete(trace_id: TraceId) -> None:
        """Delete a trace."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT file_id FROM trace
                WHERE id = %s
                """,
                (trace_id,),
            ) as r:
                row: tuple[StorageKey] | None = await r.fetchone()
                if row is None:
                    raise_for.trace_not_found(trace_id)

            result = await conn.execute(
                """
                DELETE FROM trace
                WHERE id = %s AND user_id = %s
                """,
                (trace_id, user_id),
            )

            if not result.rowcount:
                raise_for.trace_access_denied(trace_id)

        # After successful delete, also remove the file
        await TRACE_STORAGE.delete(row[0])


@cython.cfunc
def _get_file_name(file: UploadFile) -> str:
    """
    Get the file name from the upload file.

    If not provided, use the current time as the file name.
    """
    filename = file.filename
    return filename if (filename is not None) else f'{utcnow().isoformat(timespec="seconds")}.gpx'
