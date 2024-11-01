import logging

import cython
from httpx import Timeout
from shapely import Point, get_coordinates

from app.config import OVERPASS_INTERPRETER_URL
from app.limits import OVERPASS_CACHE_EXPIRE
from app.models.overpass import OverpassElement
from app.services.cache_service import CacheContext, CacheService
from app.utils import HTTP, JSON_DECODE

_cache_context = CacheContext('Overpass')


class OverpassQuery:
    @staticmethod
    async def nearby_elements(point: Point, radius_meters: float) -> list[OverpassElement]:
        """
        Query Overpass for elements nearby a point.

        Results are sorted by size in ascending order, with the smallest element first.
        """
        x, y = get_coordinates(point)[0].tolist()
        timeout = 10
        query = (
            f'[out:json][timeout:{timeout}];'  #
            f'nwr(around:{radius_meters},{y:.7f},{x:.7f});'
            'out geom qt;'
        )

        async def factory() -> bytes:
            logging.debug('Querying Overpass for nearby elements at %r with radius %r', point, radius_meters)
            r = await HTTP.post(
                OVERPASS_INTERPRETER_URL,
                data={'data': query},
                timeout=Timeout(timeout * 2),
            )
            r.raise_for_status()
            return r.content

        cache = await CacheService.get(query, _cache_context, factory, ttl=OVERPASS_CACHE_EXPIRE)
        elements_data: list[OverpassElement] = JSON_DECODE(cache.value)['elements']
        elements_data.sort(key=_sort_by_bounds)
        return elements_data

    @staticmethod
    async def enclosing_elements(point: Point) -> list['OverpassElement']:
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
            'out geom qt;'
            'rel(pivot.a);'
            'out geom qt;'
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
        elements_data: list[OverpassElement] = JSON_DECODE(cache.value)['elements']
        elements_data.sort(key=_sort_by_bounds)
        return elements_data


@cython.cfunc
def _sort_by_bounds(element: 'OverpassElement'):
    if element['type'] == 'node':
        return (0, -element['id'])
    bounds = element['bounds']
    minlon: cython.double = bounds['minlon']
    minlat: cython.double = bounds['minlat']
    maxlon: cython.double = bounds['maxlon']
    maxlat: cython.double = bounds['maxlat']
    size = (maxlon - minlon) * (maxlat - minlat)
    return (1, size)
