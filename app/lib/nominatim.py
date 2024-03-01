import logging
from collections.abc import Sequence
from urllib.parse import urlencode

from httpx import HTTPError
from shapely import Polygon, box, get_coordinates
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
from app.models.nominatim_result import NominatimResult
from app.services.cache_service import CacheService
from app.utils import HTTP, JSON_DECODE

_cache_context = 'Nominatim'


class Nominatim:
    @staticmethod
    async def reverse_name(point: Point, zoom: int) -> str:
        """
        Reverse geocode a point into a human-readable name.
        """

        x, y = get_coordinates(point)[0].tolist()

        path = '/reverse?' + urlencode(
            {
                'format': 'jsonv2',
                'lon': f'{x:.7f}',
                'lat': f'{y:.7f}',
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
            return JSON_DECODE(cache_entry.value)['display_name']
        except HTTPError:
            logging.warning('Nominatim reverse geocoding failed', exc_info=True)
            # always succeed, return coordinates as a fallback
            return f'{y:.5f}, {x:.5f}'

    @staticmethod
    async def search(*, q: str, bounds: Polygon | None = None) -> NominatimResult:
        """
        Search for a location by name.

        Returns the first result as a NominatimSearchGeneric object.
        """

        path = '/search?' + urlencode(
            {
                'format': 'jsonv2',
                'q': q,
                'limit': NOMINATIM_SEARCH_RESULTS_LIMIT,
                **({'viewbox': ','.join(f'{x:.7f}' for x in bounds.bounds)} if (bounds is not None) else {}),
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
        result: dict = JSON_DECODE(cache_entry.value)[0]

        point = Point(float(result['lon']), float(result['lat']))
        name = result['display_name']
        result_bbox = result['boundingbox']
        miny = float(result_bbox[0])
        maxy = float(result_bbox[1])
        minx = float(result_bbox[2])
        maxx = float(result_bbox[3])
        geometry = box(minx, miny, maxx, maxy)

        return NominatimResult(point=point, name=name, bounds=geometry)

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
                **({'viewbox': ','.join(f'{x:.7f}' for x in bounds.bounds)} if (bounds is not None) else {}),
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
        results: list[dict] = JSON_DECODE(cache_entry.value)

        return tuple(
            ElementRef(osm_type, osm_id)
            for result in results
            # some results are abstract and have no osm_type/osm_id
            if (osm_type := result.get('osm_type')) is not None and (osm_id := result.get('osm_id')) is not None
        )
