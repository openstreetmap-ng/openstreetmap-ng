from fastapi import APIRouter, HTTPException
from starlette.responses import Response

from app.lib.geo.gps_tiles import GPS_MASTER_ZOOM
from app.queries.gps_tile_query import GPSTileQuery

router = APIRouter(prefix='/gps/lines')


@router.get('/{z}/{x}/{y}')
@router.get('/{z}/{x}/{y}.png')
async def tile(z: int, x: int, y: int):
    if not 0 <= z <= GPS_MASTER_ZOOM or not 0 <= x < 1 << z or not 0 <= y < 1 << z:
        raise HTTPException(400, 'Invalid GPS tile coordinates')
    return Response(await GPSTileQuery.render(z, x, y), media_type='image/png')
