from asyncio import TaskGroup
from io import BytesIO
from math import asinh, atan, pi, radians, sinh, tan

from fastapi import APIRouter, HTTPException, Response
from PIL import Image, ImageDraw
from shapely import MultiLineString, box, get_coordinates
from starlette import status

from app.queries.trace_query import TraceQuery

router = APIRouter()

_TILE_SIZE = 256
_MAX_ZOOM = 23
_TRACE_COLOR = (0, 102, 255, 190)


@router.get('/gps/lines/{z:int}/{x:int}/{y:int}')
@router.get('/gps/lines/{z:int}/{x:int}/{y:int}.png')
@router.get('/lines/{z:int}/{x:int}/{y:int}')
@router.get('/lines/{z:int}/{x:int}/{y:int}.png')
async def gps_trace_tile(z: int, x: int, y: int):
    """Render public GPX traces into an anonymous transparent raster tile."""
    _validate_tile(z, x, y)
    geometry = _tile_geometry(z, x, y)

    async with TaskGroup() as tg:
        identifiable_t = tg.create_task(
            TraceQuery.find_by_geom(
                geometry,
                identifiable_trackable=True,
                limit=5000,
            )
        )
        anonymous_t = tg.create_task(
            TraceQuery.find_by_geom(
                geometry,
                identifiable_trackable=False,
                limit=5000,
            )
        )

    image = Image.new('RGBA', (_TILE_SIZE, _TILE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    for trace in (*identifiable_t.result(), *anonymous_t.result()):
        _draw_segments(draw, trace['segments'], z=z, x=x, y=y)

    buffer = BytesIO()
    image.save(buffer, format='PNG', optimize=True)
    return Response(
        buffer.getvalue(),
        media_type='image/png',
        headers={'Cache-Control': 'public, max-age=3600'},
    )


def _validate_tile(z: int, x: int, y: int):
    if z < 0 or z > _MAX_ZOOM:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    tiles = 1 << z
    if x < 0 or x >= tiles or y < 0 or y >= tiles:
        raise HTTPException(status.HTTP_404_NOT_FOUND)


def _tile_geometry(z: int, x: int, y: int):
    return box(
        _tile_x_to_lon(x, z),
        _tile_y_to_lat(y + 1, z),
        _tile_x_to_lon(x + 1, z),
        _tile_y_to_lat(y, z),
    )


def _tile_x_to_lon(x: int, z: int):
    return x / (1 << z) * 360 - 180


def _tile_y_to_lat(y: int, z: int):
    return atan(sinh(pi * (1 - 2 * y / (1 << z)))) * 180 / pi


def _draw_segments(
    draw: ImageDraw.ImageDraw,
    segments: MultiLineString,
    *,
    z: int,
    x: int,
    y: int,
):
    for line in segments.geoms:
        coords = get_coordinates(line)
        if len(coords) == 0:
            continue

        points = [
            _lonlat_to_tile_pixel(float(lon), float(lat), z=z, x=x, y=y)
            for lon, lat in coords[:, :2]
        ]
        if len(points) == 1:
            px, py = points[0]
            draw.ellipse((px - 1, py - 1, px + 1, py + 1), fill=_TRACE_COLOR)
        else:
            draw.line(points, fill=_TRACE_COLOR, width=2, joint='curve')


def _lonlat_to_tile_pixel(lon: float, lat: float, *, z: int, x: int, y: int):
    scale = 1 << z
    world_x = (lon + 180) / 360 * scale
    world_y = (1 - asinh(tan(radians(lat))) / pi) / 2 * scale
    return (
        (world_x - x) * _TILE_SIZE,
        (world_y - y) * _TILE_SIZE,
    )
