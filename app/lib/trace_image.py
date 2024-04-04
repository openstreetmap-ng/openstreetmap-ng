import logging
from collections.abc import Sequence
from io import StringIO
from typing import Final

import cython
import drawsvg as draw
from shapely import Point, get_coordinates

from app.lib.mercator import mercator
from app.models.db.trace_point import TracePoint

if cython.compiled:
    from cython.cimports.libc.math import ceil
else:
    from math import ceil


class TraceImage:
    image_suffix: Final[str] = '.svg'
    icon_suffix: Final[str] = '.svg'

    @staticmethod
    def generate(trace_points: Sequence[TracePoint]) -> tuple[bytes, bytes]:
        """
        Generate animation and icon images from a sequence of trace points.
        """

        svg_size: int = 100
        anim_frames: cython.int = 10
        anim_delay: cython.int = 500

        primary_color = 'black'
        primary_width: float = 1.2
        secondary_color = '#bbb'
        secondary_width: float = 0.4

        # get shapely points from trace points
        points: tuple[Point] = tuple(tp.point for tp in trace_points)
        points_len: cython.int = len(points)

        # sample points to speed up image generation
        sample_points_per_frame: cython.int = 20
        max_points: cython.int = sample_points_per_frame * anim_frames

        if points_len > max_points:
            step: cython.int = (points_len - 1) // (max_points - 1)
            num_indices: cython.int = int(ceil(points_len / step))

            # make sure we always include the last point, nice visually
            points = (*points[::step], points[-1]) if (num_indices > max_points) else points[::step]
            points_len: cython.int = len(points)

        logging.debug('Generating %d frames animation for %d points', anim_frames, points_len)

        coords: list[int] = mercator(get_coordinates(points), svg_size, svg_size).astype(int).flatten().tolist()

        anim_d = draw.Drawing(
            svg_size + primary_width,
            svg_size + primary_width,
            (primary_width / -2, primary_width / -2),
            animation_config=draw.types.SyncedAnimationConfig(
                duration=anim_frames * anim_delay / 1000,
            ),
        )
        anim_d.append(
            draw.Lines(
                *coords,
                fill='none',
                stroke=secondary_color,
                stroke_width=secondary_width,
                stroke_linecap='round',
            )
        )

        i: cython.int
        for i in range(anim_frames):
            i_start: cython.int = i * sample_points_per_frame
            i_end: cython.int = (i + 1) * sample_points_per_frame
            time_start: cython.double = i * anim_delay / 1000
            time_end: cython.double = (i + 1) * anim_delay / 1000

            section = coords[i_start * 2 : (i_end + 1) * 2]

            line = draw.Lines(
                *section,
                fill='none',
                stroke=primary_color,
                stroke_width=primary_width,
                stroke_linecap='round',
            )

            if i > 0:
                line.add_key_frame(time_start, display='none')
            line.add_key_frame(time_start, display='block')
            line.add_key_frame(time_end, display='none')

            anim_d.append(line)

        with StringIO() as f:
            anim_d.as_svg(f)
            anim = f.getvalue()

        # make line thicker for icon
        primary_width = 2

        icon_d = draw.Drawing(
            svg_size + primary_width,
            svg_size + primary_width,
            (primary_width / -2, primary_width / -2),
            animation_config=draw.types.SyncedAnimationConfig(
                duration=anim_frames * anim_delay / 1000,
            ),
        )
        icon_d.append(
            draw.Lines(
                *coords,
                fill='none',
                stroke=primary_color,
                stroke_width=primary_width,
                stroke_linecap='round',
            )
        )

        with StringIO() as f:
            icon_d.as_svg(f)
            icon = f.getvalue()

        return anim.encode(), icon.encode()
