import logging
from abc import ABC
from collections.abc import Sequence
from io import BytesIO
from itertools import chain
from math import ceil

import anyio
from PIL import Image, ImageDraw
from PIL.Image import Resampling

from cython_lib.mercator import Mercator
from models.db.trace_point import TracePoint

_SAMPLE_POINTS_PER_FRAME = 20

_ANTIALIAS = 4
_ANIM_FRAMES = 10
_ANIM_DELAY = 500
_ANIM_GEN_SIZE = 250 * _ANTIALIAS
_ANIM_GEN_SIZE_T = _ANIM_GEN_SIZE, _ANIM_GEN_SIZE
_ANIM_SAVE_SIZE_T = _ANIM_GEN_SIZE // _ANTIALIAS, _ANIM_GEN_SIZE // _ANTIALIAS

_ICON_DOWNSCALE = 5
_ICON_SAVE_SIZE_T = _ANIM_SAVE_SIZE_T[0] // _ICON_DOWNSCALE, _ANIM_SAVE_SIZE_T[1] // _ICON_DOWNSCALE

_BACKGROUND_COLOR = 255
_PRIMARY_COLOR = 0
_PRIMARY_WIDTH = 3 * _ANTIALIAS
_SECONDARY_COLOR = 187
_SECONDARY_WIDTH = 1 * _ANTIALIAS


class TracksImage(ABC):
    image_suffix = '.webp'
    icon_suffix = '.webp'

    @staticmethod
    async def generate_async(points: Sequence[TracePoint]) -> tuple[bytes, bytes]:
        """
        Generate animation and icon images from a sequence of trace points.
        """

        # Pillow frees the GIL when doing image operations
        return await anyio.to_thread.run_sync(TracksImage.generate, points)

    @staticmethod
    def generate(points: Sequence[TracePoint]) -> tuple[bytes, bytes]:
        """
        Generate animation and icon images from a sequence of trace points.
        """

        # sample points to speed up image generation
        max_points = _SAMPLE_POINTS_PER_FRAME * _ANIM_FRAMES
        if len(points) > max_points:
            step = (len(points) - 1) // (max_points - 1)
            indices = tuple(range(0, len(points), step))
            if len(indices) > max_points:
                # make sure we always include the last point (nice visually)
                indices = chain(indices[: max_points - 1], (len(points) - 1,))
            points = tuple(points[i] for i in indices)

        logging.debug('Generating %d frames animation for %d points', _ANIM_FRAMES, len(points))

        min_lon, max_lon = min(p.point.x for p in points), max(p.point.x for p in points)
        min_lat, max_lat = min(p.point.y for p in points), max(p.point.y for p in points)

        proj = Mercator(min_lon, min_lat, max_lon, max_lat, _ANIM_GEN_SIZE, _ANIM_GEN_SIZE)
        points_proj = tuple((proj.x(p.point.x), proj.y(p.point.y)) for p in points)
        points_per_frame = ceil(len(points) / _ANIM_FRAMES)

        # animation generation
        # L = luminance (grayscale)
        base_frame = Image.new('L', _ANIM_GEN_SIZE_T, color=_BACKGROUND_COLOR)
        draw = ImageDraw.Draw(base_frame)
        draw.line(points_proj, fill=_SECONDARY_COLOR, width=_SECONDARY_WIDTH, joint=None)

        frames = [None] * _ANIM_FRAMES

        for n in range(_ANIM_FRAMES):
            start_idx = n * points_per_frame
            end_idx = start_idx + points_per_frame  # no need to clamp, slicing does it for us

            frame = base_frame.copy()
            draw = ImageDraw.Draw(frame)
            draw.line(points_proj[start_idx : end_idx + 1], fill=_PRIMARY_COLOR, width=_PRIMARY_WIDTH, joint='curve')

            frame = frame.resize(_ANIM_SAVE_SIZE_T, Resampling.BOX)
            frames[n] = frame

        animation = BytesIO()
        frames[0].save(
            animation,
            save_all=True,
            append_images=frames[1:],
            duration=_ANIM_DELAY,
            loop=0,
            format='WEBP',
            lossless=True,
        )

        # icon generation
        base_frame = Image.new('L', _ANIM_GEN_SIZE_T, color=_BACKGROUND_COLOR)
        draw = ImageDraw.Draw(base_frame)
        draw.line(points_proj, fill=_PRIMARY_COLOR, width=_SECONDARY_WIDTH * _ICON_DOWNSCALE + 10, joint=None)
        base_frame = base_frame.resize(_ICON_SAVE_SIZE_T, Resampling.BOX)

        icon = BytesIO()
        base_frame.save(icon, format='WEBP', lossless=True)

        return animation.getvalue(), icon.getvalue()
