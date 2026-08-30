from collections.abc import Iterable, Mapping
from io import BytesIO
from math import atan, cos, degrees, log, pi, radians, sinh, tan
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Response
from PIL import Image, ImageDraw
from shapely import box, get_coordinates, set_srid
from starlette import status

from app.config import TRACE_POINT_QUERY_DEFAULT_LIMIT
from app.queries.trace_query import TraceQuery

router = APIRouter(prefix='/gps/lines')

_TILE_SIZE = 256
_MAX_MERCATOR_LAT = 85.0511287798066
_TRACE_LINE_FILL = (0, 100, 255, 120)


@router.get('/{z:int}/{x:int}/{y:int}')
@router.get('/{z:int}/{x:int}/{y:int}.png')
async def get_gps_line_tile(
    z: Annotated[int, Path(ge=0, le=30)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
):
    if not trace_tile_is_valid(z, x, y):
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    geometry = trace_tile_bounds(z, x, y)

    traces = await TraceQuery.find_by_geom(
        geometry,
        visibility=['identifiable', 'public'],
        limit=TRACE_POINT_QUERY_DEFAULT_LIMIT,
    )

    png = render_trace_tile(traces, z, x, y)
    return Response(
        png,
        media_type='image/png',
        headers={'Cache-Control': 'public, max-age=300'},
    )


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


def trace_tile_is_valid(z: int, x: int, y: int):
    if z < 0:
        return False
    n = 1 << z
    return 0 <= x < n and 0 <= y < n


def render_trace_tile(traces: Iterable[Mapping[str, Any]], z: int, x: int, y: int):
    image = Image.new('RGBA', (_TILE_SIZE, _TILE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, 'RGBA')

    for trace in traces:
        for line in trace['segments'].geoms:
            coords = get_coordinates(line)
            if len(coords) < 2:
                continue

            points = [
                _project_lonlat_to_tile(lon, lat, z=z, x=x, y=y) for lon, lat in coords
            ]
            draw.line(points, fill=_TRACE_LINE_FILL, width=1)

    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def _tile_x_to_lon(x: int, n: int):
    return x / n * 360.0 - 180.0


def _tile_y_to_lat(y: int, n: int):
    return degrees(atan(sinh(pi * (1 - (2 * y / n)))))


def _project_lonlat_to_tile(
    lon: float,
    lat: float,
    *,
    z: int,
    x: int,
    y: int,
):
    lat = min(max(lat, -_MAX_MERCATOR_LAT), _MAX_MERCATOR_LAT)
    lat_rad = radians(lat)
    n = 1 << z

    world_x = (lon + 180.0) / 360.0 * n
    world_y = (1 - log(tan(lat_rad) + 1 / cos(lat_rad)) / pi) / 2 * n

    return (
        (world_x - x) * _TILE_SIZE,
        (world_y - y) * _TILE_SIZE,
    )
