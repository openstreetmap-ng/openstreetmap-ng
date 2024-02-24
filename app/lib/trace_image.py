import logging
from collections.abc import Sequence
from io import BytesIO
from typing import Final

import cython
from anyio import to_thread
from PIL import Image, ImageDraw
from PIL.Image import Resampling
from shapely import Point, get_coordinates

from app.lib.mercator import Mercator
from app.models.db.trace_point import TracePoint

if cython.compiled:
    from cython.cimports.libc.math import ceil
else:
    from math import ceil


class TraceImage:
    image_suffix: Final[str] = '.webp'
    icon_suffix: Final[str] = '.webp'

    @staticmethod
    async def generate_async(points: Sequence[TracePoint]) -> tuple[bytes, bytes]:
        """
        Generate animation and icon images from a sequence of trace points.
        """

        # Pillow frees the GIL when doing some image operations
        return await to_thread.run_sync(TraceImage.generate, points)

    @staticmethod
    def generate(trace_points: Sequence[TracePoint]) -> tuple[bytes, bytes]:
        """
        Generate animation and icon images from a sequence of trace points.
        """

        # configuration, types optimized for cython<->python conversion in loops
        sample_points_per_frame: cython.int = 20
        antialias: cython.int = 4

        anim_frames: cython.int = 10
        anim_delay: int = 500
        anim_gen_size: cython.int = 250 * antialias
        anim_gen_size_tuple: tuple[int, int] = (anim_gen_size, anim_gen_size)
        anim_save_size_tuple: tuple[int, int] = (
            anim_gen_size // antialias,
            anim_gen_size // antialias,
        )

        icon_downscale: cython.int = 5
        icon_save_size_tuple: tuple[int, int] = (
            anim_gen_size // icon_downscale // antialias,
            anim_gen_size // icon_downscale // antialias,
        )

        background_color: int = 255
        primary_color: int = 0
        primary_width: cython.int = 3 * antialias
        secondary_color: int = 187
        secondary_width: cython.int = 1 * antialias

        # get shapely points from trace points
        points: tuple[Point] = tuple(tp.point for tp in trace_points)
        points_len: cython.int = len(points)

        # sample points to speed up image generation
        max_points: cython.int = sample_points_per_frame * anim_frames

        if points_len > max_points:
            step: cython.int = (points_len - 1) // (max_points - 1)
            num_indices: cython.int = int(ceil(points_len / step))

            # make sure we always include the last point, nice visually
            points = tuple(*points[::step], points[-1]) if (num_indices > max_points) else points[::step]
            points_len: cython.int = len(points)

        logging.debug('Generating %d frames animation for %d points', anim_frames, points_len)

        points_coords = []

        # find bounding box without python's builtin min/max
        min_lon: cython.double = 180
        max_lon: cython.double = -180
        min_lat: cython.double = 90
        max_lat: cython.double = -90

        for p in points:
            coords = get_coordinates(p)[0].tolist()
            points_coords.append(coords)
            x: cython.double = coords[0]
            y: cython.double = coords[1]

            if x < min_lon:
                min_lon = x
            if x > max_lon:
                max_lon = x
            if y < min_lat:
                min_lat = y
            if y > max_lat:
                max_lat = y

        mercator = Mercator(min_lon, min_lat, max_lon, max_lat, anim_gen_size, anim_gen_size)
        project_x = mercator.x
        project_y = mercator.y
        projected_coords = [(project_x(x), project_y(y)) for x, y in points_coords]

        # animation generation, L = luminance (grayscale)
        base_frame = Image.new('L', anim_gen_size_tuple, color=background_color)
        draw = ImageDraw.Draw(base_frame)
        draw.line(projected_coords, fill=secondary_color, width=secondary_width, joint=None)

        points_per_frame: cython.int = int(ceil(points_len / anim_frames))
        frames = []

        i: cython.int
        for i in range(anim_frames):
            start_idx: cython.int = i * points_per_frame
            end_idx: cython.int = start_idx + points_per_frame  # no need to clamp, slicing does it for us

            frame = base_frame.copy()
            draw = ImageDraw.Draw(frame)
            draw.line(projected_coords[start_idx : end_idx + 1], fill=primary_color, width=primary_width, joint='curve')

            frame = frame.resize(anim_save_size_tuple, Resampling.BOX)
            frames.append(frame)

        with BytesIO() as buffer:
            frames[0].save(
                buffer,
                save_all=True,
                append_images=frames[1:],
                duration=anim_delay,
                loop=0,
                format='WEBP',
                lossless=True,
            )

            animation = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()

            # icon generation
            base_frame = Image.new('L', anim_gen_size_tuple, color=background_color)
            draw = ImageDraw.Draw(base_frame)
            draw.line(projected_coords, fill=primary_color, width=secondary_width * icon_downscale + 10, joint=None)
            base_frame = base_frame.resize(icon_save_size_tuple, Resampling.BOX)

            base_frame.save(
                buffer,
                format='WEBP',
                lossless=True,
            )

            icon = buffer.getvalue()

        return animation, icon
