import logging
from abc import ABC
from collections.abc import Sequence
from io import BytesIO
from itertools import chain
from math import ceil

from anyio import to_thread
from PIL import Image, ImageDraw
from PIL.Image import Resampling

from app.lib_cython.mercator import Mercator
from app.models.db.trace_point import TracePoint

_sample_points_per_frame = 20

_antialias = 4
_anim_frames = 10
_anim_delay = 500
_anim_gen_size = 250 * _antialias
_anim_gen_size_tuple = _anim_gen_size, _anim_gen_size
_anim_save_size_tuple = _anim_gen_size // _antialias, _anim_gen_size // _antialias

_icon_downscale = 5
_icon_save_size_tuple = _anim_save_size_tuple[0] // _icon_downscale, _anim_save_size_tuple[1] // _icon_downscale

_background_color = 255
_primary_color = 0
_primary_width = 3 * _antialias
_secondary_color = 187
_secondary_width = 1 * _antialias


class TracksImage(ABC):
    image_suffix = '.webp'
    icon_suffix = '.webp'

    @staticmethod
    async def generate_async(points: Sequence[TracePoint]) -> tuple[bytes, bytes]:
        """
        Generate animation and icon images from a sequence of trace points.
        """

        # Pillow frees the GIL when doing some image operations
        return await to_thread.run_sync(TracksImage.generate, points)

    @staticmethod
    def generate(points: Sequence[TracePoint]) -> tuple[bytes, bytes]:
        """
        Generate animation and icon images from a sequence of trace points.
        """

        # sample points to speed up image generation
        max_points = _sample_points_per_frame * _anim_frames

        if len(points) > max_points:
            step = (len(points) - 1) // (max_points - 1)
            indices = tuple(range(0, len(points), step))

            # make sure we always include the last point (nice visually)
            if len(indices) > max_points:
                indices = chain(indices[: max_points - 1], (len(points) - 1,))

            points = tuple(points[i] for i in indices)

        logging.debug('Generating %d frames animation for %d points', _anim_frames, len(points))

        min_lon, max_lon = min(p.point.x for p in points), max(p.point.x for p in points)
        min_lat, max_lat = min(p.point.y for p in points), max(p.point.y for p in points)

        proj = Mercator(min_lon, min_lat, max_lon, max_lat, _anim_gen_size, _anim_gen_size)
        points_proj = tuple((proj.x(p.point.x), proj.y(p.point.y)) for p in points)
        points_per_frame = ceil(len(points) / _anim_frames)

        # animation generation
        # L = luminance (grayscale)
        base_frame = Image.new('L', _anim_gen_size_tuple, color=_background_color)
        draw = ImageDraw.Draw(base_frame)
        draw.line(points_proj, fill=_secondary_color, width=_secondary_width, joint=None)

        frames = [None] * _anim_frames

        for n in range(_anim_frames):
            start_idx = n * points_per_frame
            end_idx = start_idx + points_per_frame  # no need to clamp, slicing does it for us

            frame = base_frame.copy()
            draw = ImageDraw.Draw(frame)
            draw.line(points_proj[start_idx : end_idx + 1], fill=_primary_color, width=_primary_width, joint='curve')

            frame = frame.resize(_anim_save_size_tuple, Resampling.BOX)
            frames[n] = frame

        with BytesIO() as buffer:
            frames[0].save(
                buffer,
                save_all=True,
                append_images=frames[1:],
                duration=_anim_delay,
                loop=0,
                format='WEBP',
                lossless=True,
            )

            animation = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()

            # icon generation
            base_frame = Image.new('L', _anim_gen_size_tuple, color=_background_color)
            draw = ImageDraw.Draw(base_frame)
            draw.line(points_proj, fill=_primary_color, width=_secondary_width * _icon_downscale + 10, joint=None)
            base_frame = base_frame.resize(_icon_save_size_tuple, Resampling.BOX)

            base_frame.save(
                buffer,
                format='WEBP',
                lossless=True,
            )

            icon = buffer.getvalue()
        return animation, icon
