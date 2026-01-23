import logging
from asyncio import get_running_loop
from typing import Any

import cython
from fastapi import UploadFile
from sentry_sdk import capture_exception

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
    validate_trace_tags,
)
from app.models.types import StorageKey, TraceId
from app.queries.trace_query import TraceQuery
from app.services.audit_service import audit


class TraceService:
    @staticmethod
    async def upload(
        file: UploadFile,
        *,
        description: str,
        tags: str | list[str] | None,
        visibility: TraceVisibility,
    ) -> TraceId:
        """Process upload of a trace file. Returns the created trace id."""
        tags = validate_trace_tags(tags)

        file_size = file.size
        if file_size is None or file_size > TRACE_FILE_UPLOAD_MAX_SIZE:
            raise_for.input_too_big(file_size or -1)
        file_bytes = await file.read()

        try:
            tracks: list[dict] = []
            for gpx_bytes in TraceFile.extract(file_bytes):
                new_tracks = XMLToDict.parse(gpx_bytes).get('gpx', {}).get('trk', [])  # type: ignore
                tracks.extend(new_tracks)
        except Exception as e:
            raise_for.bad_trace_file(str(e))

        decoded = FormatGPX.decode_tracks(tracks)
        logging.debug(
            'Organized %d points into %d segments',
            decoded.size,
            len(decoded.segments.geoms),
        )

        trace_init: TraceInit = {
            'user_id': auth_user(required=True)['id'],
            'name': _get_file_name(file),
            'description': description,
            'tags': tags,
            'visibility': visibility,
            'file_id': StorageKey(''),
            'size': decoded.size,
            'segments': decoded.segments,
            'elevations': decoded.elevations,
            'capture_times': decoded.capture_times,
        }
        trace_init = TraceInitValidator.validate_python(trace_init)

        # Save the compressed file after validation to avoid unnecessary work
        result = await TraceFile.compress(file_bytes)
        trace_init['file_id'] = await TRACE_STORAGE.save(
            result.data, result.suffix, result.metadata
        )
        logging.debug('Saved compressed trace file %r', trace_init['file_id'])

        try:
            # Insert into database
            async with db(True) as conn:
                async with await conn.execute(
                    """
                    INSERT INTO trace (
                        user_id, name, description, tags, visibility,
                        file_id, size, segments, elevations, capture_times
                    ) VALUES (
                        %(user_id)s, %(name)s, %(description)s, %(tags)s, %(visibility)s,
                        %(file_id)s, %(size)s, ST_QuantizeCoordinates(%(segments)s, 7), %(elevations)s, %(capture_times)s
                    )
                    RETURNING id
                    """,
                    trace_init,
                ) as r:
                    trace_id: TraceId = (await r.fetchone())[0]  # type: ignore

                await audit(
                    'create_trace',
                    conn,
                    extra={
                        'id': trace_id,
                        'name': trace_init['name'],
                        'description': trace_init['description'],
                        'tags': trace_init['tags'],
                        'visibility': trace_init['visibility'],
                    },
                )

        except Exception:
            # Clean up trace file on error
            await TRACE_STORAGE.delete(trace_init['file_id'])
            raise

        # Start background recompression task
        loop = get_running_loop()
        loop.create_task(_recompress_task(trace_id, file_bytes))  # noqa: RUF006

        return trace_id

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
        trace = await TraceQuery.get_by_id(trace_id)

        audit_extra: dict[str, Any] = {'id': trace_id}
        if trace['name'] != name:
            audit_extra['name'] = name
        if trace['description'] != description:
            audit_extra['description'] = description
        if set(trace['tags']).symmetric_difference(tags):
            audit_extra['tags'] = tags
        if trace['visibility'] != visibility:
            audit_extra['visibility'] = visibility

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
                raise_for.trace_access_denied(trace_id)

            if len(audit_extra) > 1:
                await audit('update_trace', conn, extra=audit_extra)

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

            await audit('delete_trace', conn, extra={'id': trace_id})

        # After successful delete, also remove the file
        await TRACE_STORAGE.delete(row[0])


@cython.cfunc
def _get_file_name(file: UploadFile) -> str:
    """
    Get the file name from the upload file.

    If not provided, use the current time as the file name.
    """
    return file.filename or f'{utcnow().isoformat(timespec="seconds")}.gpx'


async def _recompress_task(trace_id: TraceId, file_bytes: bytes) -> None:
    """
    Background task to recompress the trace file with heavy compression.

    This improves storage efficiency without delaying the upload response.
    """
    try:
        logging.debug('Starting background recompression for trace %d', trace_id)

        # Compress with heavy settings (level 22)
        result = await TraceFile.compress_heavy(file_bytes)
        new_file_id = await TRACE_STORAGE.save(result.data, result.suffix, result.metadata)
        logging.debug('Saved recompressed trace file %r', new_file_id)

        # Update the trace to point to the new file
        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT file_id FROM trace
                WHERE id = %s
                FOR UPDATE
                """,
                (trace_id,),
            ) as r:
                row = await r.fetchone()
                if row is None:
                    # Trace was deleted, clean up new file
                    logging.debug('Trace %d was deleted, cleaning up recompressed file', trace_id)
                    await TRACE_STORAGE.delete(new_file_id)
                    return

                old_file_id = row[0]

            await conn.execute(
                """
                UPDATE trace
                SET file_id = %s
                WHERE id = %s
                """,
                (new_file_id, trace_id),
            )

        # Delete the old file after successful update
        await TRACE_STORAGE.delete(old_file_id)
        logging.info('Completed background recompression for trace %d', trace_id)

    except Exception:
        logging.warning('Failed background recompression for trace %d', trace_id, exc_info=True)
        capture_exception()
