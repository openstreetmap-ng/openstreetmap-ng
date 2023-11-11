import logging
from abc import ABC
from itertools import count
from math import isclose
from typing import Sequence

import anyio
import magic
from fastapi import UploadFile

from db.transaction import Transaction, retry_transaction
from lib.auth import Auth
from lib.exceptions import Exceptions
from lib.format.format06 import Format06
from lib.storage import LocalStorage, Storage
from lib.tracks.image import TracksImage
from lib.tracks.processors import TRACKS_PROCESSORS, ZstdTracksProcessor
from limits import TRACE_FILE_MAX_SIZE
from models.db.lock import lock
from models.db.trace import Trace
from models.db.trace_point import TracePoint
from models.trace_visibility import TraceVisibility

_LOCK_TTL = 30


class Tracks(ABC):
    storage: Storage = LocalStorage('tracks')

    @staticmethod
    async def process_upload(file: UploadFile, description: str, tags: str, visibility: TraceVisibility) -> Trace:
        if len(file.size) > TRACE_FILE_MAX_SIZE:
            Exceptions.get().raise_for_input_too_big(len(file.size))

        buffer = await anyio.to_thread.run_sync(file.file.read)
        points: list[TracePoint] = []
        trace: Trace = None
        image: bytes = None
        icon: bytes = None
        compressed: bytes = None
        compressed_suffix: str = None

        async def extract_and_generate(buffer: bytes) -> None:
            nonlocal trace, points, image, icon

            for file in await _extract(buffer):
                try:
                    points.extend(Format06.decode_gpx(file))
                except Exception as e:
                    Exceptions.get().raise_for_bad_trace_file(str(e))

            if len(points) < 2:
                Exceptions.get().raise_for_bad_trace_file('not enough points')

            points = _sort_and_deduplicate(points)

            # construct trace model first, to validate the fields
            trace = Trace(
                user_id=Auth.user().id,
                name=file.filename,
                description=description,
                size=len(points),
                start_point=points[0].point,
                visibility=visibility)
            trace.tag_string = tags

            image, icon = await TracksImage.generate_async(points)

        async def compress(buffer: bytes) -> None:
            nonlocal compressed, compressed_suffix
            compressed, compressed_suffix = await _compress(buffer)

        async with anyio.create_task_group() as tg:
            tg.start_soon(extract_and_generate, buffer)
            tg.start_soon(compress, buffer)

        file_id: str = None
        image_id: str = None
        icon_id: str = None

        async def save_file() -> None:
            nonlocal file_id
            file_id = await Tracks.storage.save(compressed, compressed_suffix)

        async def save_image() -> None:
            nonlocal image_id
            image_id = await Tracks.storage.save(image, TracksImage.image_suffix)

        async def save_icon() -> None:
            nonlocal icon_id
            icon_id = await Tracks.storage.save(icon, TracksImage.icon_suffix)

        # when all validation is done, save the files
        async with anyio.create_task_group() as tg:
            tg.start_soon(save_file)
            tg.start_soon(save_image)
            tg.start_soon(save_icon)

        trace.file_id = file_id
        trace.image_id = image_id
        trace.icon_id = icon_id

        await _create(trace, points)
        return trace

    @staticmethod
    async def get_file(file_id: str) -> bytes:
        buffer = await Tracks.storage.load(file_id)
        return await _decompress_if_needed(buffer, file_id)


async def _extract(buffer: bytes) -> Sequence[bytes]:
    '''
    Extracts the trace files from the buffer.

    The buffer may be compressed, in which case it will be decompressed first.
    '''

    # multiple layers handle combinations such as tar+gzip
    for layer in count(1):
        if layer > 2:
            Exceptions.get().raise_for_trace_file_archive_too_deep()

        content_type = magic.from_buffer(buffer[:2048], mime=True)
        logging.debug('Trace file layer %d is %r', layer, content_type)

        if not (processor := TRACKS_PROCESSORS.get(content_type)):
            Exceptions.get().raise_for_trace_file_unsupported_format(content_type)

        result = await processor.decompress(buffer)

        if isinstance(result, bytes):
            # further processing is needed
            buffer = result
        else:
            # finished processing
            return result


def _sort_and_deduplicate(points: Sequence[TracePoint]) -> Sequence[TracePoint]:
    '''
    Sorts and deduplicates the points.

    The points are sorted by captured_at, then by longitude, then by latitude.
    '''

    sorted_points = sorted(points, key=lambda p: (p.captured_at, p.point.x, p.point.y))
    deduped_points = [sorted_points[0]]

    for last, point in zip(sorted_points, sorted_points[1:]):
        if last.captured_at == point.captured_at and \
                isclose(last.point.x, point.point.x, abs_tol=9.999e-8) and \
                isclose(last.point.y, point.point.y, abs_tol=9.999e-8):  # different up to 7 decimal places
            continue
        deduped_points.append(point)

    return deduped_points


async def _compress(buffer: bytes) -> tuple[bytes, str]:
    '''
    Compresses the buffer with zstd.
    '''

    return await ZstdTracksProcessor.compress(buffer), ZstdTracksProcessor.suffix


async def _decompress_if_needed(buffer: bytes, file_id: str) -> bytes:
    '''
    Decompresses the buffer if needed.
    '''

    if file_id.endswith(ZstdTracksProcessor.suffix):
        return await ZstdTracksProcessor.decompress(buffer)

    return buffer


@retry_transaction()
async def _create(trace: Trace, points: Sequence[TracePoint]) -> None:
    trace.id = None

    # use lock since points size can be very large (create batch may be slow)
    async with (
            lock(Trace.__class__.__qualname__, ttl=_LOCK_TTL),
            Transaction() as session):
        await trace.create(session)

        bulk = []
        for point in points:
            point.trace_id = trace.id
            bulk.append(point.create_batch())

        await TracePoint._collection().bulk_write(bulk, ordered=False, session=session)
