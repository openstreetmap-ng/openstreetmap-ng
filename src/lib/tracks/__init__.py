import logging
from collections.abc import Sequence
from datetime import timedelta
from itertools import pairwise

import anyio
import magic
from anyio import to_thread
from fastapi import UploadFile

from src.db import DB
from src.lib.exceptions import raise_for
from src.lib.format.format06 import Format06
from src.lib.storage import TRACKS_STORAGE
from src.lib.tracks.image import TracksImage
from src.lib.tracks.processors import TRACE_FILE_PROCESSORS
from src.lib.tracks.processors.zstd import ZstdFileProcessor
from src.lib_cython.auth import auth_user
from src.lib_cython.xmltodict import XMLToDict
from src.limits import TRACE_FILE_MAX_SIZE
from src.models.db.trace_ import Trace
from src.models.db.trace_point import TracePoint
from src.models.trace_visibility import TraceVisibility
from src.models.validating.trace_ import TraceValidating


class Tracks:
    @staticmethod
    async def process_upload(file: UploadFile, description: str, tags: str, visibility: TraceVisibility) -> Trace:
        """
        Process the uploaded trace file.

        Returns the created trace object.
        """

        if len(file.size) > TRACE_FILE_MAX_SIZE:
            raise_for().input_too_big(len(file.size))

        buffer = await to_thread.run_sync(file.file.read)
        points: list[TracePoint] = []
        trace: Trace = None
        image: bytes = None
        icon: bytes = None
        compressed: bytes = None
        compressed_suffix: str = None

        async def extract_and_generate_image_icon() -> None:
            nonlocal trace, points, image, icon

            track_idx_last = -1

            # process multiple files in the archive
            for gpx_b in await _extract(buffer):
                try:
                    gpx = gpx_b.decode()
                    tracks = XMLToDict.parse(gpx).get('gpx', {}).get('trk', [])
                    points.extend(Format06.decode_tracks(tracks, track_idx_start=track_idx_last + 1))
                except Exception as e:
                    raise_for().bad_trace_file(str(e))

                if points:
                    track_idx_last = points[-1].track_idx

            points = _sort_and_deduplicate(points)

            # require two distinct points: sane bounding box and icon
            if len(points) < 2:
                raise_for().bad_trace_file('not enough points')

            trace = Trace(
                **TraceValidating(
                    user_id=auth_user().id,
                    name=file.filename,
                    description=description,
                    visibility=visibility,
                    size=len(points),
                    start_point=points[0].point,
                    tags=(),  # set with .tag_string
                ).to_orm_dict()
            )

            trace.points = points
            trace.tag_string = tags

            image, icon = await TracksImage.generate_async(points)

        async def compress_upload() -> None:
            nonlocal compressed, compressed_suffix
            compressed, compressed_suffix = await _zstd_compress(buffer)

        async with anyio.create_task_group() as tg:
            tg.start_soon(extract_and_generate_image_icon)
            tg.start_soon(compress_upload)

        file_id: str = None
        image_id: str = None
        icon_id: str = None

        async def save_file() -> None:
            nonlocal file_id
            file_id = await TRACKS_STORAGE.save(compressed, compressed_suffix)

        async def save_image() -> None:
            nonlocal image_id
            image_id = await TRACKS_STORAGE.save(image, TracksImage.image_suffix)

        async def save_icon() -> None:
            nonlocal icon_id
            icon_id = await TRACKS_STORAGE.save(icon, TracksImage.icon_suffix)

        # save the files after the validation
        async with anyio.create_task_group() as tg:
            tg.start_soon(save_file)
            tg.start_soon(save_image)
            tg.start_soon(save_icon)

        trace.file_id = file_id
        trace.image_id = image_id
        trace.icon_id = icon_id

        async with DB() as session, session.begin():
            session.add(trace)

        return trace

    @staticmethod
    async def get_file(file_id: str) -> bytes:
        """
        Get the trace file by id.
        """

        buffer = await TRACKS_STORAGE.load(file_id)
        return await _zstd_decompress_if_needed(buffer, file_id)


async def _extract(buffer: bytes) -> Sequence[bytes]:
    """
    Extract the trace files from the buffer.

    The buffer may be compressed, in which case it will be decompressed first.
    """

    # multiple layers allow to handle nested archives
    # such as .tar.gz
    for layer in (1, 2):
        content_type = magic.from_buffer(buffer[:2048], mime=True)
        logging.debug('Trace file layer %d is %r', layer, content_type)

        # get the appropriate processor
        if not (processor := TRACE_FILE_PROCESSORS.get(content_type)):
            raise_for().trace_file_unsupported_format(content_type)

        result = await processor.decompress(buffer)

        # bytes: further processing is needed
        if isinstance(result, bytes):
            buffer = result
            continue

        # list of bytes: finished
        return result

    # raise on too many layers
    raise_for().trace_file_archive_too_deep()


def _sort_and_deduplicate(points: Sequence[TracePoint]) -> Sequence[TracePoint]:
    """
    Sort and deduplicates the points.

    The points are sorted by captured_at, then by longitude, then by latitude.
    """

    max_pos_diff = 1e-7  # different up to 7 decimal places
    max_date_diff = timedelta(seconds=1)

    sorted_points = sorted(points, key=lambda p: (p.captured_at, p.point.x, p.point.y))
    deduped_points = [sorted_points[0]]

    for prev, point in pairwise(sorted_points):
        if (
            abs(point.point.x - prev.point.x) < max_pos_diff
            and abs(point.point.y - prev.point.y) < max_pos_diff
            and point.captured_at - prev.captured_at < max_date_diff  # check date last, slowest to compute
        ):
            continue
        deduped_points.append(point)

    return deduped_points


async def _zstd_compress(buffer: bytes) -> tuple[bytes, str]:
    """
    Compress the buffer with zstd.
    """

    return await ZstdFileProcessor.compress(buffer), ZstdFileProcessor.suffix


async def _zstd_decompress_if_needed(buffer: bytes, file_id: str) -> bytes:
    """
    Decompress the buffer if needed.
    """

    if file_id.endswith(ZstdFileProcessor.suffix):
        return await ZstdFileProcessor.decompress(buffer)

    return buffer
