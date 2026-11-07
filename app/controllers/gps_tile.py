from asyncio import to_thread

from fastapi import APIRouter, HTTPException, Response

from app.lib.geo.gps_tile import GPS_TILE_MAX_ZOOM, gps_tile_bounds, render_gps_tile
from app.queries.gps_tile_query import GPSTileQuery

router = APIRouter(prefix='/gps/lines')


@router.get('/{z:int}/{x:int}/{y:int}.png')
@router.get('/{z:int}/{x:int}/{y:int}')
async def gps_tile(z: int, x: int, y: int):
    if not (0 <= z <= GPS_TILE_MAX_ZOOM and 0 <= x < 1 << z and 0 <= y < 1 << z):
        raise HTTPException(404, 'Invalid GPS tile coordinates')
    lines = await GPSTileQuery.find_lines(gps_tile_bounds(z, x, y))
    # Rendering is CPU work; do not block the event loop.
    content = await to_thread(render_gps_tile, lines, z, x, y)
    return Response(
        content,
        media_type='image/png',
        headers={'Cache-Control': 'public, max-age=60'},
    )
