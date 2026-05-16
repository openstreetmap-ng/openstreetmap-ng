import logging
from asyncio import get_running_loop
from typing import Any

from fastapi import UploadFile
from sentry_sdk import capture_exception
from zstandard import ZstdCompressor

from app.config import TRACE_FILE_UPLOAD_MAX_SIZE, TRACE_FILE_RECOMPRESS_ZSTD_LEVEL
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
    normalize_trace_tags,
)
from app.models.proto.trace_types import Visibility
from app.models.types import StorageKey, TraceId
from app.queries.trace_query import TraceQuery
from app.services.audit_service import audit


class TraceService:
    @staticmethod
    async def upload(
        file: UploadFile | bytes,
        *,
        name: str | None,
        description: str,
        tags: list[str],
        visibility: Visibility,
    ) -> TraceId:
        """Process upload of a trace file. Returns the created trace id."""
        tags = normalize_trace_tags(tags)

        if isinstance(file, bytes):
            if len(file) > TRACE_FILE_UPLOAD_MAX_SIZE:
                raise_for.input_too_big(len(file))
        else:
            file_size = file.size
            if file_size is None or file_size > TRACE_FILE_UPLOAD_MAX_SIZE:
                raise_for.input_too_big(file_size or -1)
            if name is None:
                name = file.filename
            file = await file.read()

        try:
            tracks: list[dict] = []
            for gpx_bytes in TraceFile.extract(file):
                new_tracks = XMLToDict.parse(gpx_bytes).get('gpx', {}).get('trk', [])
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
            'name': name or f'{utcnow().isoformat(timespec="seconds")}.gpx',
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
        result = await TraceFile.compress(file)
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

            # Start background recompression with heavier zstd level
            loop = get_running_loop()
            loop.create_task(  # noqa: RUF006
                _recompress_trace(trace_id, file, trace_init['file_id'])
            )

            return trace_id

        except Exception:
            # Clean up trace file on error
            await TRACE_STORAGE.delete(trace_init['file_id'])
            raise

    @staticmethod
    async def update(
        trace_id: TraceId,
        *,
        name: str,
        description: str,
        tags: list[str],
        visibility: Visibility,
    ):
        """Update a trace."""
        user_id = auth_user(required=True)['id']
        trace = await TraceQuery.get_by_id(trace_id)
        tags = normalize_trace_tags(tags)

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
    async def delete(trace_id: TraceId):
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


async def _recompress_trace(
    trace_id: TraceId,
    file_bytes: bytes,
    old_file_id: StorageKey,
) -> None:
    """Background task: recompress trace file with heavier zstd level.

    After recompression, updates the trace's file_id in the database
    and deletes the old (lightly compressed) file from storage.
    """
    try:
        loop = get_running_loop()
        recompressed = await loop.run_in_executor(
            None,
            ZstdCompressor(level=TRACE_FILE_RECOMPRESS_ZSTD_LEVEL).compress,
            file_bytes,
        )

        new_metadata = {'zstd_level': str(TRACE_FILE_RECOMPRESS_ZSTD_LEVEL)}
        new_file_id = await TRACE_STORAGE.save(recompressed, '.zst', new_metadata)
        logging.debug(
            'Recompressed trace %d: %d -> %d bytes',
            trace_id,
            len(file_bytes),
            len(recompressed),
        )

        # Update the trace to point to the new file
        async with db(True) as conn:
            result = await conn.execute(
                """
                UPDATE trace
                SET file_id = %s
                WHERE id = %s AND file_id = %s
                """,
                (new_file_id, trace_id, old_file_id),
            )

            if result.rowcount:
                # Trace was updated successfully, delete the old file
                await TRACE_STORAGE.delete(old_file_id)
                logging.info(
                    'Trace %d recompressed: file %r -> %r',
                    trace_id,
                    old_file_id,
                    new_file_id,
                )
            else:
                # Trace was deleted or file_id changed concurrently, clean up new file
                await TRACE_STORAGE.delete(new_file_id)
                logging.debug(
                    'Trace %d skipped recompression (file_id changed or trace deleted)',
                    trace_id,
                )

    except Exception:
        capture_exception()
