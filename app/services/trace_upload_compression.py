import logging

from sentry_sdk import capture_exception

from app.db import db_update
from app.lib.io.trace_file import TraceFile
from app.lib.storage import TRACE_STORAGE
from app.models.types import StorageKey, TraceId


async def compress_trace_upload(
    trace_id: TraceId,
    old_file_id: StorageKey,
    file: bytes,
):
    """Compress a trace upload and atomically replace the stored file reference."""
    compressed_file_id: StorageKey | None = None
    try:
        result = await TraceFile.compress(file)
        compressed_file_id = await TRACE_STORAGE.save(
            result.data, result.suffix, result.metadata
        )
        logging.debug('Saved compressed trace file %r', compressed_file_id)

        rowcount = await db_update(
            'trace',
            {'file_id': compressed_file_id},
            where={'id': trace_id, 'file_id': old_file_id},
        )

        if rowcount:
            await TRACE_STORAGE.delete(old_file_id)
        else:
            await TRACE_STORAGE.delete(compressed_file_id)

    except Exception as e:
        logging.exception('Failed to compress trace file %r', old_file_id)
        capture_exception(e)
        if compressed_file_id is not None:
            try:
                await TRACE_STORAGE.delete(compressed_file_id)
            except Exception as cleanup_error:
                logging.exception(
                    'Failed to clean up compressed trace file %r',
                    compressed_file_id,
                )
                capture_exception(cleanup_error)
