from asyncio import TaskGroup
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from math import atan, degrees, log, pi, radians, sinh, tan
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path
from PIL import Image, ImageDraw
from psycopg import IsolationLevel
from psycopg.sql import SQL
from psycopg.sql import Literal as PgLiteral
from shapely import LineString, MultiLineString, Polygon, box, get_coordinates
from starlette import status
from starlette.responses import Response

from app.db import db
from app.lib.geo_utils import polygon_to_h3
from app.queries.timescaledb_query import TimescaleDBQuery

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
            _find_tile_segments(
                bounds.geometry,
                identifiable_trackable=True,
                limit=_MAX_TRACES_PER_TILE,
            )
        )
        anonymous_t = tg.create_task(
            _find_tile_segments(
                bounds.geometry,
                identifiable_trackable=False,
                limit=_MAX_TRACES_PER_TILE,
            )
        )

    tile = _render_png_tile([*identifiable_t.result(), *anonymous_t.result()], bounds)
    return Response(tile, media_type='image/png', headers=headers)


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


async def _find_tile_segments(
    geometry: Polygon,
    *,
    identifiable_trackable: bool,
    limit: int,
) -> list[MultiLineString]:
    """Find only trace geometry needed for a public GPS tile."""
    params: dict[str, Any] = {
        'h3_cells': polygon_to_h3(geometry, max_resolution=11),
        'visibility': (
            ['identifiable', 'trackable']
            if identifiable_trackable
            else ['public', 'private']
        ),
        'limit': limit,
    }

    async with db(isolation_level=IsolationLevel.REPEATABLE_READ) as conn:
        query = SQL("""
            /*+ BitmapScan(trace trace_segments_idx) */
            {query}
            LIMIT %(limit)s
        """).format(
            query=SQL(' UNION ALL ').join([
                SQL("""(
                    SELECT segments FROM trace
                    WHERE h3_points_to_cells_range(segments, 11) && %(h3_cells)s::h3index[]
                    AND visibility = ANY(%(visibility)s)
                    AND id BETWEEN {chunk_start} AND {chunk_end}
                    ORDER BY id DESC
                )""").format(
                    chunk_start=PgLiteral(chunk_start),
                    chunk_end=PgLiteral(chunk_end),
                )
                for chunk_start, chunk_end in await TimescaleDBQuery.get_chunks_ranges(
                    'trace', conn
                )
            ])
        )

        async with await conn.execute(query, params) as r:
            segments_list = [segments for (segments,) in await r.fetchall()]

    if not segments_list:
        return []

    lines = [
        line
        for segments in segments_list
        for line in _iter_lines(segments.intersection(geometry))
    ]
    if not lines:
        return []

    if identifiable_trackable:
        return [MultiLineString([line]) for line in lines]

    return [MultiLineString(lines)]


def _tile_lat(y: int, n: int) -> float:
    return degrees(atan(sinh(pi * (1 - 2 * y / n))))


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


def _project_point(lon: float, lat: float, bounds: _TileBounds):
    x = (lon - bounds.west) / (bounds.east - bounds.west) * _TILE_SIZE
    y = (
        (bounds.north_mercator - _mercator_y(lat))
        / (bounds.north_mercator - bounds.south_mercator)
        * _TILE_SIZE
    )
    return x, y
