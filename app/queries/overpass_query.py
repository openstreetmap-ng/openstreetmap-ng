import logging
from typing import Any

import cython
from httpx import Timeout
from shapely import Point, get_coordinates

from app.config import OVERPASS_INTERPRETER_URL
from app.limits import OVERPASS_CACHE_EXPIRE
from app.models.db.element import Element
from app.services.cache_service import CacheContext, CacheService
from app.utils import HTTP, JSON_DECODE

_cache_context = CacheContext('Overpass')


class OverpassQuery:
    @staticmethod
    async def enclosing_elements(point: Point) -> tuple[Element, ...]:
        """
        Query Overpass for elements enclosing by a point.

        Results are sorted by size in ascending order, with the smallest element first.

        Returns simplified element instances.
        """
        x, y = get_coordinates(point)[0].tolist()
        timeout = 10
        query = (
            f'[out:json][timeout:{timeout}];'
            f'is_in({y:.7f},{x:.7f})->.a;'  # lat,lon
            'way(pivot.a);'
            'out tags bb;'
            'rel(pivot.a);'
            'out tags bb;'
        )

        async def factory() -> bytes:
            logging.debug('Querying Overpass for enclosing elements at %r', point)
            r = await HTTP.post(
                OVERPASS_INTERPRETER_URL,
                data={'data': query},
                timeout=Timeout(timeout * 2),
            )
            r.raise_for_status()
            return r.content

        cache = await CacheService.get(query, _cache_context, factory, ttl=OVERPASS_CACHE_EXPIRE)
        elements: list[dict[str, Any]] = JSON_DECODE(cache.value)['elements']  # pyright: ignore[reportInvalidTypeForm]
        elements.sort(key=_get_bounds_size)

        return tuple(
            Element(
                changeset_id=0,
                type=element['type'],
                id=element['id'],
                version=0,
                visible=True,
                tags=element['tags'],
                point=None,
            )
            for element in elements
        )


@cython.cfunc
def _get_bounds_size(element: dict) -> float:
    bounds: dict = element['bounds']
    minlon: cython.double = bounds['minlon']
    minlat: cython.double = bounds['minlat']
    maxlon: cython.double = bounds['maxlon']
    maxlat: cython.double = bounds['maxlat']
    size = (maxlon - minlon) * (maxlat - minlat)
    return size
