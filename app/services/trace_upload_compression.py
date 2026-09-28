import logging
from asyncio import TaskGroup, get_running_loop
from types import TracebackType

from sentry_sdk import capture_exception

from app.db import db_update
from app.lib.io.trace_file import TraceFile
from app.lib.storage import TRACE_STORAGE
from app.models.types import StorageKey, TraceId

_COMPRESSION_TG: TaskGroup | None = None


class _CompressionContext:
    def __init__(self):
        self._tg = TaskGroup()

    async def __aenter__(self):
        global _COMPRESSION_TG
        await self._tg.__aenter__()
        _COMPRESSION_TG = self._tg
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ):
        global _COMPRESSION_TG
        try:
            for task in self._tg._tasks:  # noqa: SLF001
                task.cancel()
            return await self._tg.__aexit__(exc_type, exc, tb)
        finally:
            _COMPRESSION_TG = None


class TraceUploadCompressionService:
    @staticmethod
    def context():
        """Context manager for trace upload compression tasks."""
        return _CompressionContext()

    @staticmethod
    def schedule(trace_id: TraceId, old_file_id: StorageKey, file: bytes):
        """Schedule trace upload compression without blocking the response."""
        if _COMPRESSION_TG is None:
            get_running_loop().create_task(  # noqa: RUF006
                compress_trace_upload(trace_id, old_file_id, file)
            )
            return

        _COMPRESSION_TG.create_task(compress_trace_upload(trace_id, old_file_id, file))


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
