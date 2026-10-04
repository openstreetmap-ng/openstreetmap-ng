from collections.abc import Iterable, Mapping
from io import BytesIO
from math import asinh, atan, degrees, pi, radians, sinh, tan
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Response
from PIL import Image, ImageDraw
from shapely import box, get_coordinates, set_srid
from starlette import status

from app.config import TRACE_POINT_QUERY_DEFAULT_LIMIT
from app.queries.trace_query import TraceQuery

router = APIRouter(prefix='/gps/lines')

_TILE_SIZE = 256
_TRACE_LINE_FILL = (0, 100, 255, 120)

# Pre-render a transparent empty 256x256 PNG for cache and query efficiency
_EMPTY_TILE_PNG: bytes
with BytesIO() as _buf:
    Image.new('RGBA', (_TILE_SIZE, _TILE_SIZE), (0, 0, 0, 0)).save(_buf, format='PNG')
    _EMPTY_TILE_PNG = _buf.getvalue()


def trace_tile_is_valid(z: int, x: int, y: int) -> bool:
    if z < 0 or z > 20:
        return False
    n = 1 << z
    return 0 <= x < n and 0 <= y < n


def _tile_x_to_lon(x: int, n: int) -> float:
    return x / n * 360.0 - 180.0


def _tile_y_to_lat(y: int, n: int) -> float:
    lat_rad = atan(sinh(pi * (1.0 - 2.0 * y / n)))
    return degrees(lat_rad)


def trace_tile_bounds(z: int, x: int, y: int):
    n = 1 << z
    return set_srid(
        box(
            _tile_x_to_lon(x, n),
            _tile_y_to_lat(y + 1, n),
            _tile_x_to_lon(x + 1, n),
            _tile_y_to_lat(y, n),
        ),
        4326,
    )


def _lon_to_px(lon: float, z: int, tile_x: int) -> float:
    return ((lon + 180.0) / 360.0 * (1 << z) - tile_x) * _TILE_SIZE


def _lat_to_px(lat: float, z: int, tile_y: int) -> float:
    lat_rad = radians(lat)
    lat_rad = max(min(lat_rad, 1.4844222), -1.4844222)
    return ((1.0 - asinh(tan(lat_rad)) / pi) / 2.0 * (1 << z) - tile_y) * _TILE_SIZE


def render_trace_tile(
    traces: Iterable[Mapping[str, Any]], z: int, x: int, y: int
) -> bytes:
    image = Image.new('RGBA', (_TILE_SIZE, _TILE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, 'RGBA')
    has_lines = False

    for trace in traces:
        segments = trace.get('segments')
        if segments is None or not hasattr(segments, 'geoms'):
            continue
        for line in segments.geoms:
            coords = get_coordinates(line)
            if len(coords) < 2:
                continue
            pixel_points = [
                (_lon_to_px(lon, z, x), _lat_to_px(lat, z, y)) for lon, lat in coords
            ]
            draw.line(pixel_points, fill=_TRACE_LINE_FILL, width=1)
            has_lines = True

    if not has_lines:
        return _EMPTY_TILE_PNG

    with BytesIO() as buf:
        image.save(buf, format='PNG')
        return buf.getvalue()


@router.get('/{z:int}/{x:int}/{y:int}')
@router.get('/{z:int}/{x:int}/{y:int}.png')
async def get_gps_line_tile(
    z: Annotated[int, Path(ge=0, le=20)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
):
    if not trace_tile_is_valid(z, x, y):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail='Tile coordinates out of bounds'
        )

    geometry = trace_tile_bounds(z, x, y)
    traces = await TraceQuery.find_by_geom(
        geometry,
        visibility=['identifiable', 'public'],
        limit=TRACE_POINT_QUERY_DEFAULT_LIMIT,
    )

    if not traces:
        return Response(
            _EMPTY_TILE_PNG,
            media_type='image/png',
            headers={'Cache-Control': 'public, max-age=300'},
        )

    png_bytes = render_trace_tile(traces, z, x, y)
    return Response(
        png_bytes,
        media_type='image/png',
        headers={'Cache-Control': 'public, max-age=300'},
    )
