import logging
from asyncio import TaskGroup
from collections.abc import Iterable, Sequence
from typing import NotRequired, TypedDict
from urllib.parse import urlencode

import numpy as np
import orjson
from httpx import Timeout
from shapely import MultiPolygon, Point, Polygon, get_coordinates, lib

from app.config import NOMINATIM_URL
from app.lib.feature_icon import features_icons
from app.lib.feature_prefix import features_prefixes
from app.lib.search import SearchResult
from app.lib.translation import primary_translation_locale
from app.limits import (
    NOMINATIM_CACHE_LONG_EXPIRE,
    NOMINATIM_CACHE_SHORT_EXPIRE,
    NOMINATIM_HTTP_LONG_TIMEOUT,
    NOMINATIM_HTTP_SHORT_TIMEOUT,
)
from app.models.db.element import Element
from app.models.element import ElementId, ElementRef, ElementType
from app.queries.element_query import ElementQuery
from app.services.cache_service import CacheContext, CacheService
from app.utils import HTTP

_HTTP_SHORT_TIMEOUT = Timeout(NOMINATIM_HTTP_SHORT_TIMEOUT.total_seconds())
_HTTP_LONG_TIMEOUT = Timeout(NOMINATIM_HTTP_LONG_TIMEOUT.total_seconds())

_cache_context = CacheContext('Nominatim')

# https://nominatim.org/release-docs/develop/api/Search/
# https://nominatim.org/release-docs/develop/api/Reverse/
# https://nominatim.org/release-docs/develop/api/Output/


class NominatimPlace(TypedDict):
    place_id: int
    osm_type: NotRequired[ElementType]
    osm_id: NotRequired[ElementId]
    boundingbox: tuple[str, str, str, str]
    lat: str
    lon: str
    display_name: str
    category: str
    type: str
    place_rank: int
    importance: float
    icon: str


class NominatimQuery:
    @staticmethod
    async def reverse(point: Point, zoom: int = 14) -> SearchResult | None:
        """
        Reverse geocode a point into a human-readable name.
        """
        x, y = get_coordinates(point)[0].tolist()
        path = '/reverse?' + urlencode(
            {
                'format': 'jsonv2',
                'lon': f'{x:.5f}',
                'lat': f'{y:.5f}',
                'zoom': zoom,
                'accept-language': primary_translation_locale(),
            }
        )

        async def factory() -> bytes:
            logging.debug('Nominatim reverse cache miss for path %r', path)
            r = await HTTP.get(NOMINATIM_URL + path, timeout=_HTTP_SHORT_TIMEOUT)
            r.raise_for_status()
            return r.content

        cache = await CacheService.get(
            path,
            context=_cache_context,
            factory=factory,
            ttl=NOMINATIM_CACHE_LONG_EXPIRE,
        )
        response_entries = (orjson.loads(cache.value),)
        result = await _get_search_result(at_sequence_id=None, response_entries=response_entries)
        return next(iter(result), None)

    @staticmethod
    async def search(
        *,
        q: str,
        bounds: Polygon | MultiPolygon | None = None,
        at_sequence_id: int | None,
        limit: int,
    ) -> list[SearchResult]:
        """
        Search for a location by name and optional bounds.
        """
        polygons = bounds.geoms if isinstance(bounds, MultiPolygon) else (bounds,)

        async with TaskGroup() as tg:
            tasks = tuple(
                tg.create_task(
                    _search(
                        q=q,
                        bounds=polygon,
                        at_sequence_id=at_sequence_id,
                        limit=limit,
                    )
                )
                for polygon in polygons
            )

        # results are sorted from highest to lowest importance
        return sorted(
            (result for task in tasks for result in task.result()),
            key=lambda r: r.importance,
            reverse=True,
        )


async def _search(
    *,
    q: str,
    bounds: Polygon | None,
    at_sequence_id: int | None,
    limit: int,
) -> list[SearchResult]:
    path = '/search?' + urlencode(
        {
            'format': 'jsonv2',
            'q': q,
            'limit': limit,
            **(
                {
                    'viewbox': ','.join(f'{x:.5f}' for x in bounds.bounds),
                    'bounded': 1,
                }
                if (bounds is not None)
                else {}
            ),
            'accept-language': primary_translation_locale(),
        }
    )

    async def factory() -> bytes:
        logging.debug('Nominatim search cache miss for path %r', path)
        r = await HTTP.get(NOMINATIM_URL + path, timeout=_HTTP_LONG_TIMEOUT)
        r.raise_for_status()
        return r.content

    # cache only stable queries
    if bounds is None:
        cache = await CacheService.get(
            path,
            context=_cache_context,
            factory=factory,
            hash_key=True,
            ttl=NOMINATIM_CACHE_SHORT_EXPIRE,
        )
        response = cache.value
    else:
        response = await factory()

    response_entries = orjson.loads(response)
    return await _get_search_result(at_sequence_id=at_sequence_id, response_entries=response_entries)


async def _get_search_result(
    *,
    at_sequence_id: int | None,
    response_entries: Iterable[NominatimPlace],
) -> list[SearchResult]:
    """
    Convert nominatim places into search results.
    """
    refs: list[ElementRef] = []
    entries: list[NominatimPlace] = []
    for entry in response_entries:
        # some results are abstract and have no osm_type/osm_id
        osm_type = entry.get('osm_type')
        osm_id = entry.get('osm_id')
        if (osm_type is None) or (osm_id is None):
            continue

        ref = ElementRef(osm_type, osm_id)
        refs.append(ref)
        entries.append(entry)

    # fetch elements in the order of entries
    elements: Sequence[Element | None]
    elements = await ElementQuery.get_by_refs(refs, at_sequence_id=at_sequence_id, limit=len(refs))
    ref_element_map: dict[ElementRef, Element] = {ElementRef(e.type, e.id): e for e in elements}
    elements = tuple(ref_element_map.get(ref) for ref in refs)  # not all elements may be found in the database

    icons = features_icons(elements)
    prefixes = features_prefixes(elements)
    result: list[SearchResult] = []
    for entry, element, icon, prefix in zip(entries, elements, icons, prefixes, strict=True):
        # skip non-existing elements
        if element is None or not element.visible:
            continue
        if prefix is None:
            continue

        bbox = entry['boundingbox']
        miny = float(bbox[0])
        maxy = float(bbox[1])
        minx = float(bbox[2])
        maxx = float(bbox[3])
        bounds = minx, miny, maxx, maxy

        lon = (minx + maxx) / 2
        lat = (miny + maxy) / 2
        point = lib.points(np.array((lon, lat), np.float64))

        result.append(
            SearchResult(
                element=element,
                rank=entry['place_rank'],
                importance=entry['importance'],
                icon=icon,
                prefix=prefix,
                display_name=entry['display_name'],
                point=point,
                bounds=bounds,
            )
        )
    return result
