from asyncio import TaskGroup
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from math import atan, degrees, log, pi, radians, sinh, tan
from typing import Annotated

import cython
from fastapi import APIRouter, HTTPException, Path
from PIL import Image, ImageDraw
from shapely import LineString, MultiLineString, Polygon, box, get_coordinates
from starlette import status
from starlette.responses import Response

from app.queries.trace_query import TraceQuery

router = APIRouter()

_TILE_SIZE = 256
_MAX_ZOOM = 23
_MAX_TRACES_PER_TILE = 500
_TRACE_COLOR = (37, 99, 235, 190)


@router.get('/gps/lines/{z:int}/{x:int}/{y:int}')
@router.get('/gps/lines/{z:int}/{x:int}/{y:int}.png')
@router.get('/lines/{z:int}/{x:int}/{y:int}')
@router.get('/lines/{z:int}/{x:int}/{y:int}.png')
@router.get('/api/web/traces/tiles/lines/{z:int}/{x:int}/{y:int}')
@router.get('/api/web/traces/tiles/lines/{z:int}/{x:int}/{y:int}.png')
async def public_tile(
    z: Annotated[int, Path(ge=0, le=_MAX_ZOOM)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
):
    return await _tile_response(z, x, y)


async def _tile_response(
    z: int,
    x: int,
    y: int,
):
    _validate_tile(z, x, y)

    headers = {'Cache-Control': 'public, max-age=300'}

    bounds = _tile_bounds(z, x, y)
    async with TaskGroup() as tg:
        identifiable_t = tg.create_task(
            TraceQuery.find_tile_segments(
                bounds.geometry,
                identifiable_trackable=True,
                limit=_MAX_TRACES_PER_TILE,
            )
        )
        anonymous_t = tg.create_task(
            TraceQuery.find_tile_segments(
                bounds.geometry,
                identifiable_trackable=False,
                limit=_MAX_TRACES_PER_TILE,
            )
        )

    tile = _render_png_tile([*identifiable_t.result(), *anonymous_t.result()], bounds)
    return Response(tile, media_type='image/png', headers=headers)


@cython.cfunc
def _validate_tile(z: int, x: int, y: int):
    limit = 1 << z
    if x >= limit or y >= limit:
        raise HTTPException(status.HTTP_404_NOT_FOUND)


@dataclass(slots=True)
class _TileBounds:
    geometry: Polygon
    west: float
    east: float
    north_mercator: float
    south_mercator: float


def _tile_bounds(z: int, x: int, y: int):
    n = 1 << z
    west = x / n * 360 - 180
    east = (x + 1) / n * 360 - 180
    north = _tile_lat(y, n)
    south = _tile_lat(y + 1, n)
    return _TileBounds(
        geometry=box(west, south, east, north),
        west=west,
        east=east,
        north_mercator=_mercator_y(north),
        south_mercator=_mercator_y(south),
    )


@cython.cfunc
def _tile_lat(y: int, n: int) -> float:
    return degrees(atan(sinh(pi * (1 - 2 * y / n))))


@cython.cfunc
def _mercator_y(lat: float) -> float:
    return log(tan(pi / 4 + radians(lat) / 2))


def _render_png_tile(traces: list[MultiLineString], bounds: _TileBounds) -> bytes:
    image = Image.new('RGBA', (_TILE_SIZE, _TILE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    for segments in traces:
        for line in _iter_lines(segments):
            coords = get_coordinates(line)
            if len(coords) < 2:
                continue
            points = [_project_point(lon, lat, bounds) for lon, lat in coords]
            draw.line(points, fill=_TRACE_COLOR, width=2)

    buffer = BytesIO()
    image.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()


def _iter_lines(geometry) -> Iterable[LineString]:
    if isinstance(geometry, LineString):
        yield geometry
        return

    if isinstance(geometry, MultiLineString):
        yield from geometry.geoms
        return

    geoms = getattr(geometry, 'geoms', ())
    for geom in geoms:
        yield from _iter_lines(geom)


@cython.cfunc
def _project_point(lon: float, lat: float, bounds: _TileBounds):
    x = (lon - bounds.west) / (bounds.east - bounds.west) * _TILE_SIZE
    y = (
        (bounds.north_mercator - _mercator_y(lat))
        / (bounds.north_mercator - bounds.south_mercator)
        * _TILE_SIZE
    )
    return x, y
