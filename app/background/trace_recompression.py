import logging
from asyncio import CancelledError, create_task, to_thread
from compression import zstd
from typing import LiteralString, NamedTuple

from sentry_sdk import capture_exception
from sizestr import sizestr

from app.config import (
    ENV,
    TRACE_FILE_COMPRESS_ZSTD_THREADS,
    TRACE_FILE_RECOMPRESS_ZSTD_LEVEL,
)
from app.db import db_update
from app.lib.storage import TRACE_STORAGE
from app.models.types import StorageKey, TraceId


class _CompressResult(NamedTuple):
    data: bytes
    suffix: LiteralString
    metadata: dict[str, str]


_ZSTD_SUFFIX = '.zst'
_ZSTD_METADATA: dict[str, str] = {
    'zstd_level': str(TRACE_FILE_RECOMPRESS_ZSTD_LEVEL)
}
_ZSTD_OPTIONS: dict[int, int] = {
    zstd.CompressionParameter.compression_level: TRACE_FILE_RECOMPRESS_ZSTD_LEVEL,
    zstd.CompressionParameter.nb_workers: TRACE_FILE_COMPRESS_ZSTD_THREADS,
}


def schedule_trace_file_recompression(
    trace_id: TraceId, old_file_id: StorageKey, file: bytes
):
    if ENV == 'test':
        return

    coro = _recompress_trace_file(trace_id, old_file_id, file)
    try:
        create_task(coro)  # noqa: RUF006
    except RuntimeError:
        coro.close()
        logging.warning(
            'Skipping trace file recompression without a running event loop',
            exc_info=True,
        )


async def _compress_trace_file(buffer: bytes):
    result = await to_thread(
        zstd.compress,
        buffer,
        options=_ZSTD_OPTIONS,
    )
    logging.debug('Trace file zstd-recompressed size is %s', sizestr(len(result)))
    return _CompressResult(result, _ZSTD_SUFFIX, _ZSTD_METADATA)


async def _recompress_trace_file(
    trace_id: TraceId, old_file_id: StorageKey, file: bytes
):
    new_file_id: StorageKey | None = None
    replaced = False

    try:
        result = await _compress_trace_file(file)
        new_file_id = await TRACE_STORAGE.save(
            result.data, result.suffix, result.metadata
        )

        rowcount = await db_update(
            'trace',
            {'file_id': new_file_id},
            where={'id': trace_id, 'file_id': old_file_id},
        )

        if rowcount:
            replaced = True
            await TRACE_STORAGE.delete(old_file_id)
            logging.debug(
                'Recompressed trace file %r to %r for trace %d',
                old_file_id,
                new_file_id,
                trace_id,
            )
        else:
            await TRACE_STORAGE.delete(new_file_id)
            logging.debug(
                'Discarded recompressed trace file %r for trace %d',
                new_file_id,
                trace_id,
            )

    except BaseException as e:
        if new_file_id is not None and not replaced:
            try:
                await TRACE_STORAGE.delete(new_file_id)
            except Exception:
                logging.warning(
                    'Failed to clean up recompressed trace file %r',
                    new_file_id,
                    exc_info=True,
                )

        if isinstance(e, CancelledError):
            raise

        capture_exception(e)
        logging.warning(
            'Trace file recompression failed for trace %d',
            trace_id,
            exc_info=True,
        )
