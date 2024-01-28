import logging
from collections.abc import Sequence

import cython
import orjson
from shapely.geometry import Point

from app.config import OVERPASS_INTERPRETER_URL
from app.limits import OVERPASS_CACHE_EXPIRE
from app.models.db.element import Element
from app.models.element_type import ElementType
from app.services.cache_service import CacheService
from app.utils import HTTP

_cache_context = 'Overpass'


def _get_bounds_size(element: dict) -> float:
    bounds: dict = element['bounds']
    minlon: cython.double = bounds['minlon']
    minlat: cython.double = bounds['minlat']
    maxlon: cython.double = bounds['maxlon']
    maxlat: cython.double = bounds['maxlat']
    size = (maxlon - minlon) * (maxlat - minlat)
    return size


class Overpass:
    @staticmethod
    async def enclosing_elements(point: Point) -> Sequence[Element]:
        """
        Query Overpass for elements enclosing by a point.

        Results are sorted by size in ascending order, with the smallest element first.

        Returns a sequence of simplified element instances.
        """

        timeout = 10
        query = (
            f'[out:json][timeout:{timeout}];'
            f'is_in({point.y:.7f},{point.x:.7f})->.a;'  # lat,lon
            'way(pivot.a);'
            'out tags bb;'
            'rel(pivot.a);'
            'out tags bb;'
        )

        async def factory() -> str:
            logging.debug('Querying Overpass for enclosing elements at %r', point)
            r = await HTTP.post(OVERPASS_INTERPRETER_URL, data={'data': query}, timeout=timeout * 2)
            r.raise_for_status()
            return r.text

        cache_entry = await CacheService.get_one_by_key(query, _cache_context, factory, ttl=OVERPASS_CACHE_EXPIRE)
        text = cache_entry.value

        elements: list[dict] = orjson.loads(text)['elements']
        elements.sort(key=_get_bounds_size)

        return tuple(
            Element(
                id=element['id'],
                type=ElementType.from_str(element['type']),
                tags=element['tags'],
            )
            for element in elements
        )
