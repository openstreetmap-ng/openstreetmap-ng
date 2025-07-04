from datetime import timedelta
from typing import Annotated
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Path, Request, Response, status
from osm_shortlink import shortlink_decode
from starlette.responses import RedirectResponse

from app.middlewares.cache_control_middleware import cache_control

router = APIRouter()


@router.get('/go/{code}')
@cache_control(max_age=timedelta(days=30), stale=timedelta(days=30))
async def shortlink(
    request: Request, code: Annotated[str, Path(min_length=3, max_length=15)]
):
    """
    Redirect to a map from a shortlink code.
    https://wiki.openstreetmap.org/wiki/Shortlink
    """
    try:
        lon, lat, z = shortlink_decode(code)
    except Exception:
        return Response('Invalid shortlink code', status.HTTP_400_BAD_REQUEST)

    fragment = '#' + urlencode(
        {'map': [f'{z}/{lat:.5f}/{lon:.5f}']}, doseq=True, quote_via=quote
    )
    if query := request.url.query:
        query = '?' + query
    return RedirectResponse(f'/{query}{fragment}', status.HTTP_301_MOVED_PERMANENTLY)
