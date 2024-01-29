import logging
from collections.abc import Sequence
from urllib.parse import urlencode

import orjson
from httpx import HTTPError
from shapely import Polygon
from shapely.geometry import Point

from app.config import NOMINATIM_URL
from app.lib.translation import primary_translation_language
from app.limits import NOMINATIM_CACHE_EXPIRE, NOMINATIM_HTTP_TIMEOUT, NOMINATIM_SEARCH_RESULTS_LIMIT
from app.models.element_type import ElementType
from app.models.typed_element_ref import TypedElementRef
from app.services.cache_service import CacheService
from app.utils import HTTP

# uses primary_translation_language for better cache hit rate

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

        async def factory() -> str:
            logging.debug('Nominatim reverse cache miss for path %r', path)
            r = await HTTP.get(NOMINATIM_URL + path, timeout=NOMINATIM_HTTP_TIMEOUT.total_seconds())
            r.raise_for_status()
            data = orjson.loads(r.content)
            return data['display_name']

        try:
            cache_entry = await CacheService.get_one_by_key(path, _cache_context, factory, ttl=NOMINATIM_CACHE_EXPIRE)
            display_name = cache_entry.value
        except HTTPError:
            logging.warning('Nominatim reverse geocoding failed', exc_info=True)
            display_name = None

        if display_name:
            return display_name
        else:
            # always succeed, return coordinates as a fallback
            return f'{point.y:.3f}, {point.x:.3f}'

    @staticmethod
    async def search(*, q: str, bbox: Polygon | None = None) -> Sequence[TypedElementRef]:
        path = '/search?' + urlencode(
            {
                'format': 'jsonv2',
                'q': q,
                'limit': NOMINATIM_SEARCH_RESULTS_LIMIT,
                **({'viewbox': ','.join(f'{x:.7f}' for x in bbox.bounds)} if bbox else {}),
                'accept-language': primary_translation_language(),
            }
        )

        async def factory() -> str:
            logging.debug('Nominatim search cache miss for path %r', path)
            r = await HTTP.get(NOMINATIM_URL + path, timeout=NOMINATIM_HTTP_TIMEOUT.total_seconds())
            r.raise_for_status()
            return r.text

        cache_entry = await CacheService.get_one_by_key(path, _cache_context, factory, ttl=NOMINATIM_CACHE_EXPIRE)
        results: list[dict] = orjson.loads(cache_entry.value)

        return tuple(
            TypedElementRef(
                type=ElementType.from_str(osm_type),
                typed_id=osm_id,
            )
            for result in results
            if (osm_type := result.get('osm_type')) and (osm_id := result.get('osm_id'))
        )
