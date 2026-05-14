import logging
from asyncio import Task, create_task
from typing import Any

from app.models.proto.trace_types import Visibility
from fastapi import UploadFile

from app.config import TRACE_FILE_UPLOAD_MAX_SIZE
from app.db import db, db_delete, db_fetchval, db_insert, db_update
from app.exceptions.context import raise_for
from app.format.gpx import FormatGPX
from app.lib.audit import audit
from app.lib.auth.context import auth_user
from app.lib.io.trace_file import TraceFile
from app.lib.io.xml_codec import XMLToDict
from app.lib.storage import TRACE_STORAGE
from app.lib.time.date_utils import utcnow
from app.models.db.trace import (
    TraceInit,
    TraceInitValidator,
    TraceMetaInit,
    TraceMetaInitValidator,
    normalize_trace_tags,
)
from app.models.types import StorageKey, TraceId
from app.queries.trace_query import TraceQuery

_HEAVY_ZSTD_LEVEL = 22
_RECOMPRESSION_TASKS: set[Task[None]] = set()


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
                segments = trace_init['segments']
                row = await db_insert(
                    'trace',
                    {
                        **trace_init,
                        'segments': t'ST_QuantizeCoordinates({segments}, 7)',
                    },
                    returning='id',
                    conn=conn,
                )
                trace_id: TraceId = row[0]

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
                _schedule_recompression(trace_id, file, trace_init['file_id'])
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
            rowcount = await db_update(
                'trace',
                {**meta_init, 'updated_at': t'DEFAULT'},
                where={'id': trace_id, 'user_id': user_id},
                conn=conn,
            )

            if not rowcount:
                raise_for.trace_access_denied(trace_id)

            if len(audit_extra) > 1:
                await audit('update_trace', conn, extra=audit_extra)

    @staticmethod
    async def delete(trace_id: TraceId):
        """Delete a trace."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            file_id = await db_fetchval(
                StorageKey,
                t'SELECT file_id FROM trace WHERE id = {trace_id}',
                conn=conn,
            )
            if file_id is None:
                raise_for.trace_not_found(trace_id)

            rowcount = await db_delete(
                'trace',
                where={'id': trace_id, 'user_id': user_id},
                conn=conn,
            )

            if not rowcount:
                raise_for.trace_access_denied(trace_id)

            await audit('delete_trace', conn, extra={'id': trace_id})

        # After successful delete, also remove the file
        await TRACE_STORAGE.delete(file_id)


def _schedule_recompression(
    trace_id: TraceId,
    file: bytes,
    old_file_id: StorageKey,
) -> None:
    task = create_task(_recompress_trace_file(trace_id, file, old_file_id))
    _RECOMPRESSION_TASKS.add(task)

    def cleanup(task: Task[None]) -> None:
        _RECOMPRESSION_TASKS.discard(task)
        if not task.cancelled() and (exc := task.exception()) is not None:
            logging.warning(
                'Trace file background recompression failed for %r',
                trace_id,
                exc_info=exc,
            )

    task.add_done_callback(cleanup)


async def _recompress_trace_file(
    trace_id: TraceId,
    file: bytes,
    old_file_id: StorageKey,
) -> None:
    result = await TraceFile.compress(file, level=_HEAVY_ZSTD_LEVEL)
    new_file_id = await TRACE_STORAGE.save(result.data, result.suffix, result.metadata)

    try:
        async with db(True) as conn:
            update_result = await conn.execute(
                """
                UPDATE trace
                SET file_id = %s
                WHERE id = %s AND file_id = %s
                """,
                (new_file_id, trace_id, old_file_id),
            )
    except Exception:
        await TRACE_STORAGE.delete(new_file_id)
        raise

    if update_result.rowcount:
        await TRACE_STORAGE.delete(old_file_id)
        logging.debug('Recompressed trace file %r -> %r', old_file_id, new_file_id)
    else:
        await TRACE_STORAGE.delete(new_file_id)
        logging.debug('Skipped trace file recompression swap for trace %r', trace_id)
