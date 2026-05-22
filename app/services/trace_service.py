import logging
from asyncio import Queue, QueueFull, TaskGroup
from contextlib import asynccontextmanager
from sys import modules
from typing import Any

from fastapi import UploadFile
from sentry_sdk import capture_exception

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
from app.models.proto.trace_types import Visibility
from app.models.types import StorageKey, TraceId
from app.queries.trace_query import TraceQuery

_RECOMPRESS_TG: TaskGroup
_RECOMPRESS_QUEUE: Queue[tuple[TraceId, StorageKey, bytes] | None]
_RECOMPRESS_QUEUE_MAX_SIZE = 1
_TESTING = 'pytest' in modules


class TraceService:
    @staticmethod
    @asynccontextmanager
    async def context():
        """Context manager for background trace work."""
        global _RECOMPRESS_QUEUE, _RECOMPRESS_TG
        _RECOMPRESS_QUEUE = Queue(_RECOMPRESS_QUEUE_MAX_SIZE)
        async with (_RECOMPRESS_TG := TaskGroup()):  # pyright: ignore[reportConstantRedefinition]
            _RECOMPRESS_TG.create_task(_recompress_worker())
            yield
            await _RECOMPRESS_QUEUE.put(None)

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

        except Exception:
            # Clean up trace file on error
            await TRACE_STORAGE.delete(trace_init['file_id'])
            raise

        # Recompress after the fast upload path has committed the trace.
        if _TESTING:
            await _recompress_task(trace_id, trace_init['file_id'], file)
        else:
            try:
                _RECOMPRESS_QUEUE.put_nowait(
                    (trace_id, trace_init['file_id'], file)
                )
            except QueueFull:
                logging.debug('Skipping trace %d recompression: queue is full', trace_id)
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
            row = await db_delete(
                'trace',
                where={'id': trace_id, 'user_id': user_id},
                returning='file_id',
                assert_returning=False,
                conn=conn,
            )

            if row is None:
                trace_exists = await db_fetchval(
                    bool,
                    t'SELECT EXISTS (SELECT 1 FROM trace WHERE id = {trace_id})',
                    conn=conn,
                )
                if not trace_exists:
                    raise_for.trace_not_found(trace_id)
                raise_for.trace_access_denied(trace_id)

            file_id: StorageKey = row[0]
            await audit('delete_trace', conn, extra={'id': trace_id})

        # After successful delete, also remove the file
        await TRACE_STORAGE.delete(file_id)


async def _recompress_task(
    trace_id: TraceId,
    old_file_id: StorageKey,
    file_bytes: bytes,
):
    """Recompress a stored trace without delaying its upload response."""
    try:
        result = await TraceFile.recompress(file_bytes)
        new_file_id = await TRACE_STORAGE.save(
            result.data, result.suffix, result.metadata
        )

        try:
            rowcount = await db_update(
                'trace',
                {'file_id': new_file_id},
                where={'id': trace_id, 'file_id': old_file_id},
            )
        except Exception:
            await TRACE_STORAGE.delete(new_file_id)
            raise

        if not rowcount:
            await TRACE_STORAGE.delete(new_file_id)
            return

        try:
            await TRACE_STORAGE.delete(old_file_id)
        except Exception:
            logging.warning(
                'Failed to delete old trace file %r after recompressing trace %d',
                old_file_id,
                trace_id,
            )
            capture_exception()

        logging.debug('Recompressed trace file %r for trace %d', new_file_id, trace_id)

    except Exception:
        logging.warning('Failed to recompress trace file for trace %d', trace_id)
        capture_exception()


async def _recompress_worker():
    """Recompress queued traces without growing upload-time work unboundedly."""
    while True:
        item = await _RECOMPRESS_QUEUE.get()
        if item is None:
            return

        await _recompress_task(*item)
