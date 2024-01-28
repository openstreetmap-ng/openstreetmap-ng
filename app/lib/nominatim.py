import logging
from urllib.parse import urlencode

import orjson
from httpx import HTTPError
from shapely.geometry import Point

from app.config import NOMINATIM_URL
from app.lib.translation import primary_translation_language
from app.limits import NOMINATIM_CACHE_EXPIRE, NOMINATIM_HTTP_TIMEOUT
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

        async def factory() -> str:
            logging.debug('Nominatim cache miss for path %r', path)
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
