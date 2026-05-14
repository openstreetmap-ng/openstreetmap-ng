import logging
from asyncio import get_running_loop
from typing import Any

from app.models.proto.trace_types import Visibility
from fastapi import UploadFile

from app.config import (
    TRACE_FILE_RECOMPRESS_ZSTD_LEVEL,
    TRACE_FILE_UPLOAD_MAX_SIZE,
)
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
        compressed_size = len(result.data)
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
        else:
            get_running_loop().create_task(
                _recompress_trace_file(
                    trace_id, trace_init['file_id'], file, compressed_size
                )
            )
            return trace_id

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


async def _recompress_trace_file(
    trace_id: TraceId,
    old_file_id: StorageKey,
    file: bytes,
    compressed_size: int,
) -> None:
    """Recompress a trace in the background and swap storage keys if still current."""
    try:
        result = await TraceFile.compress(file, level=TRACE_FILE_RECOMPRESS_ZSTD_LEVEL)
        if len(result.data) >= compressed_size:
            logging.debug(
                'Skipped trace %d recompression because level %d was not smaller',
                trace_id,
                TRACE_FILE_RECOMPRESS_ZSTD_LEVEL,
            )
            return

        new_file_id = await TRACE_STORAGE.save(
            result.data, result.suffix, result.metadata
        )
        try:
            async with db(True) as conn:
                update = await conn.execute(
                    """
                    UPDATE trace
                    SET file_id = %s
                    WHERE id = %s AND file_id = %s
                    """,
                    (new_file_id, trace_id, old_file_id),
                )

            if update.rowcount:
                await TRACE_STORAGE.delete(old_file_id)
                logging.debug(
                    'Recompressed trace %d file %r to %r',
                    trace_id,
                    old_file_id,
                    new_file_id,
                )
            else:
                await TRACE_STORAGE.delete(new_file_id)
                logging.debug(
                    'Discarded trace %d recompression because file changed',
                    trace_id,
                )
        except Exception:
            await TRACE_STORAGE.delete(new_file_id)
            raise
    except Exception:
        logging.exception('Trace %d background recompression failed', trace_id)
