import logging
from asyncio import Queue, TaskGroup, to_thread
from contextlib import asynccontextmanager
from contextvars import Context

from app.db import db, db_fetchval, db_update
from app.lib.io.trace_file import TraceFile
from app.lib.storage import TRACE_STORAGE
from app.models.types import StorageKey, TraceId

_QUEUE: Queue[tuple[TraceId, StorageKey] | None] | None = None


class TraceRecompressionService:
    @staticmethod
    @asynccontextmanager
    async def context():
        """One expensive compression at a time; drain queued work at shutdown.

        Queue IDs, not upload buffers. A fresh context keeps request/auth state
        out of this lifespan-owned worker.
        """
        global _QUEUE
        queue: Queue[tuple[TraceId, StorageKey] | None] = Queue()
        _QUEUE = queue
        try:
            async with TaskGroup() as tg:
                tg.create_task(_worker(queue), context=Context())
                try:
                    yield
                finally:
                    _QUEUE = None
                    queue.put_nowait(None)
        finally:
            _QUEUE = None

    @staticmethod
    def schedule(trace_id: TraceId, file_id: StorageKey):
        """Call only after the upload transaction has committed."""
        if _QUEUE is None:
            logging.warning('Trace recompression worker is not running')
            return
        _QUEUE.put_nowait((trace_id, file_id))

    @staticmethod
    async def drain():
        """Wait for already queued recompressions (also useful for batch jobs)."""
        if _QUEUE is not None:
            await _QUEUE.join()


async def _worker(queue: Queue[tuple[TraceId, StorageKey] | None]):
    while True:
        job = await queue.get()
        try:
            if job is None:
                return
            await _recompress(*job)
        except Exception:
            logging.exception('Background trace recompression failed for %r', job)
        finally:
            queue.task_done()


async def _recompress(trace_id: TraceId, old_file_id: StorageKey):
    current = await db_fetchval(
        StorageKey, t'SELECT file_id FROM trace WHERE id = {trace_id}'
    )
    if current != old_file_id:
        return
    try:
        buffer = await TRACE_STORAGE.load(old_file_id)
    except FileNotFoundError:
        # Deletion may have completed since the lookup.
        return
    original = await to_thread(TraceFile.decompress_if_needed, buffer, old_file_id)
    result = await TraceFile.compress(original, level=22)
    if len(result.data) >= len(buffer):
        return
    new_file_id = await TRACE_STORAGE.save(result.data, result.suffix, result.metadata)

    try:
        async with db(True) as conn:
            await db_update(
                'trace',
                {'file_id': new_file_id},
                where={'id': trace_id, 'file_id': old_file_id},
                conn=conn,
            )
    except Exception:
        # COMMIT can have succeeded before a connection error. Never blindly
        # delete the new object on this path: it may now be the live file.
        await _cleanup(trace_id, old_file_id, new_file_id)
        raise

    # Cancellation during storage/DB operations conservatively leaves objects
    # in place. Unreferenced objects are preferable to deleting a live upload.
    await _cleanup(trace_id, old_file_id, new_file_id)


async def _cleanup(trace_id: TraceId, old_file_id: StorageKey, new_file_id: StorageKey):
    try:
        current = await db_fetchval(
            StorageKey, t'SELECT file_id FROM trace WHERE id = {trace_id}'
        )
    except Exception:
        logging.exception('Retaining trace files after an uncertain database outcome')
        return
    # Each replacement key is unique and CAS only moves away from the old key.
    # Neither a competing worker nor deletion can restore a retired key.
    for file_id in (old_file_id, new_file_id):
        if file_id != current:
            await TRACE_STORAGE.delete(file_id)
