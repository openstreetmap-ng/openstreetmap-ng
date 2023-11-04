import logging
from abc import ABC
from urllib.parse import quote_plus

from httpx import HTTPError
from shapely.geometry import Point

from config import NOMINATIM_URL
from limits import NOMINATIM_CACHE_EXPIRE
from models.collections.cache import Cache
from utils import HTTP


class Nominatim(ABC):
    @staticmethod
    async def reverse_name(point: Point, zoom: int, locales: str) -> str:
        '''
        Reverse geocode a point into a human-readable name.
        '''

        path = f'/reverse?format=jsonv2&lon={point.x}&lat={point.y}&zoom={zoom}&accept-language={quote_plus(locales)}'
        cache_id = Cache.hash_key(path)
        if cached := await Cache.find_one_by_id(cache_id):
            return cached.value

        try:
            r = await HTTP.get(NOMINATIM_URL + path, timeout=4)
            r.raise_for_status()
            data = await r.json()
            display_name = data['display_name']
        except HTTPError:
            logging.warning('Nominatim reverse geocoding failed', exc_info=True)
            display_name = None

        if display_name:
            await Cache.create_from_key_id(cache_id, display_name, NOMINATIM_CACHE_EXPIRE)
        else:
            display_name = f'{point.y:.3f}, {point.x:.3f}'

        return display_name
