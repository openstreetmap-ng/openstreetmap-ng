import logging
from collections.abc import Sequence
from urllib.parse import urlencode

import orjson
from httpx import HTTPError
from shapely import Polygon, box
from shapely.geometry import Point

from app.config import NOMINATIM_URL
from app.lib.translation import primary_translation_language
from app.limits import (
    NOMINATIM_CACHE_LONG_EXPIRE,
    NOMINATIM_CACHE_SHORT_EXPIRE,
    NOMINATIM_HTTP_LONG_TIMEOUT,
    NOMINATIM_HTTP_SHORT_TIMEOUT,
    NOMINATIM_SEARCH_RESULTS_LIMIT,
)
from app.models.element_ref import ElementRef
from app.models.element_type import ElementType
from app.models.nominatim_search_generic import NominatimSearchGeneric
from app.services.cache_service import CacheService
from app.utils import HTTP

_cache_context = 'Nominatim'


class Nominatim:
    @staticmethod
    async def reverse_name(point: Point, zoom: int) -> str:
        """
        Reverse geocode a point into a human-readable name.
        """

        path = '/reverse?' + urlencode(
            {
                'format': 'jsonv2',
                'lon': f'{point.x:.7f}',
                'lat': f'{point.y:.7f}',
                'zoom': zoom,
                'accept-language': primary_translation_language(),
            }
        )

        async def factory() -> bytes:
            logging.debug('Nominatim reverse cache miss for path %r', path)
            r = await HTTP.get(NOMINATIM_URL + path, timeout=NOMINATIM_HTTP_SHORT_TIMEOUT.total_seconds())
            r.raise_for_status()
            return r.content

        try:
            cache_entry = await CacheService.get_one_by_key(
                key=path,
                context=_cache_context,
                factory=factory,
                ttl=NOMINATIM_CACHE_LONG_EXPIRE,
            )
            return orjson.loads(cache_entry.value)['display_name']
        except HTTPError:
            logging.warning('Nominatim reverse geocoding failed', exc_info=True)
            # always succeed, return coordinates as a fallback
            return f'{point.y:.5f}, {point.x:.5f}'

    @staticmethod
    async def search_generic(*, q: str, bounds: Polygon | None = None) -> NominatimSearchGeneric:
        """
        Search for a location by name.

        Returns the first result as a NominatimSearchGeneric object.
        """

        path = '/search?' + urlencode(
            {
                'format': 'jsonv2',
                'q': q,
                'limit': NOMINATIM_SEARCH_RESULTS_LIMIT,
                **({'viewbox': ','.join(f'{x:.7f}' for x in bounds.bounds)} if bounds is not None else {}),
                'accept-language': primary_translation_language(),
            }
        )

        async def factory() -> bytes:
            logging.debug('Nominatim search cache miss for path %r', path)
            r = await HTTP.get(NOMINATIM_URL + path, timeout=NOMINATIM_HTTP_LONG_TIMEOUT.total_seconds())
            r.raise_for_status()
            return r.content

        cache_entry = await CacheService.get_one_by_key(
            key=path,
            context=_cache_context,
            factory=factory,
            ttl=NOMINATIM_CACHE_SHORT_EXPIRE,
        )
        result: dict = orjson.loads(cache_entry.value)[0]

        point = Point(float(result['lon']), float(result['lat']))
        name = result['display_name']
        result_bbox = result['boundingbox']
        min_lat = float(result_bbox[0])
        max_lat = float(result_bbox[1])
        min_lon = float(result_bbox[2])
        max_lon = float(result_bbox[3])
        geometry = box(min_lon, min_lat, max_lon, max_lat)

        return NominatimSearchGeneric(point=point, name=name, bounds=geometry)

    @staticmethod
    async def search_elements(*, q: str, bounds: Polygon | None = None) -> Sequence[ElementRef]:
        """
        Search for a location by name.

        Returns a sequence of ElementRef objects.
        """

        path = '/search?' + urlencode(
            {
                'format': 'jsonv2',
                'q': q,
                'limit': NOMINATIM_SEARCH_RESULTS_LIMIT,
                **({'viewbox': ','.join(f'{x:.7f}' for x in bounds.bounds)} if bounds is not None else {}),
                'accept-language': primary_translation_language(),
            }
        )

        async def factory() -> bytes:
            logging.debug('Nominatim search cache miss for path %r', path)
            r = await HTTP.get(NOMINATIM_URL + path, timeout=NOMINATIM_HTTP_LONG_TIMEOUT.total_seconds())
            r.raise_for_status()
            return r.content

        cache_entry = await CacheService.get_one_by_key(
            key=path,
            context=_cache_context,
            factory=factory,
            ttl=NOMINATIM_CACHE_SHORT_EXPIRE,
        )
        results: list[dict] = orjson.loads(cache_entry.value)

        return tuple(
            ElementRef(
                type=ElementType.from_str(osm_type),
                id=osm_id,
            )
            for result in results
            # some results are abstract and have no osm_type/osm_id
            if (osm_type := result.get('osm_type')) is not None and (osm_id := result.get('osm_id')) is not None
        )
