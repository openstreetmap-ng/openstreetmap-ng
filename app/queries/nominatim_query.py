import logging
from asyncio import TaskGroup
from typing import NotRequired, TypedDict
from urllib.parse import urlencode

import orjson
from shapely import MultiPolygon, Point, Polygon, get_coordinates

from app.config import (
    NOMINATIM_REVERSE_CACHE_EXPIRE,
    NOMINATIM_REVERSE_HTTP_TIMEOUT,
    NOMINATIM_SEARCH_CACHE_EXPIRE,
    NOMINATIM_SEARCH_HTTP_TIMEOUT,
    NOMINATIM_URL,
)
from app.lib.crypto import hash_storage_key
from app.lib.feature_icon import features_icons
from app.lib.feature_prefix import features_prefixes
from app.lib.search import SearchResult
from app.lib.translation import primary_translation_locale
from app.models.db.element import Element
from app.models.element import ElementId, ElementType, TypedElementId
from app.models.types import SequenceId
from app.queries.element_query import ElementQuery
from app.services.cache_service import CacheContext, CacheService
from app.utils import HTTP
from speedup.element_type import typed_element_id

_CTX = CacheContext('Nominatim')

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
        """Reverse geocode a point into a human-readable name."""
        x, y = get_coordinates(point)[0].tolist()
        path = '/reverse?' + urlencode({
            'format': 'jsonv2',
            'lon': f'{x:.5f}',
            'lat': f'{y:.5f}',
            'zoom': zoom,
            'accept-language': primary_translation_locale(),
        })

        async def factory() -> bytes:
            logging.debug('Nominatim reverse cache miss for path %r', path)
            r = await HTTP.get(
                NOMINATIM_URL + path,
                timeout=NOMINATIM_REVERSE_HTTP_TIMEOUT.total_seconds(),
            )
            r.raise_for_status()
            return r.content

        key = hash_storage_key(path, '.json')
        content = await CacheService.get(
            key, _CTX, factory, ttl=NOMINATIM_REVERSE_CACHE_EXPIRE
        )
        response_entries = [orjson.loads(content)]
        result = await _get_search_result(
            at_sequence_id=None, response_entries=response_entries
        )
        return next(iter(result), None)

    @staticmethod
    async def search(
        *,
        q: str,
        bounds: Polygon | MultiPolygon | None = None,
        at_sequence_id: SequenceId | None,
        limit: int,
    ) -> list[SearchResult]:
        """Search for a location by name and optional bounds."""
        polygons = bounds.geoms if isinstance(bounds, MultiPolygon) else [bounds]

        async with TaskGroup() as tg:
            tasks = [
                tg.create_task(
                    _search(
                        q=q,
                        bounds=polygon,
                        at_sequence_id=at_sequence_id,
                        limit=limit,
                    )
                )
                for polygon in polygons
            ]

        # results are sorted from highest to lowest importance
        results = [result for task in tasks for result in task.result()]
        results.sort(key=lambda r: r.importance, reverse=True)
        return results


async def _search(
    *,
    q: str,
    bounds: Polygon | None,
    at_sequence_id: SequenceId | None,
    limit: int,
) -> list[SearchResult]:
    path = '/search?' + urlencode({
        'format': 'jsonv2',
        'q': q,
        'limit': limit,
        **(
            {
                'viewbox': ','.join(f'{x:.5f}' for x in bounds.bounds),
                'bounded': 1,
            }
            if bounds is not None
            else {}
        ),
        'accept-language': primary_translation_locale(),
    })

    async def factory() -> bytes:
        logging.debug('Nominatim search cache miss for path %r', path)
        r = await HTTP.get(
            NOMINATIM_URL + path,
            timeout=NOMINATIM_SEARCH_HTTP_TIMEOUT.total_seconds(),
        )
        r.raise_for_status()
        return r.content

    # cache only stable queries
    if bounds is None:
        key = hash_storage_key(path, '.json')
        response = await CacheService.get(
            key, _CTX, factory, ttl=NOMINATIM_SEARCH_CACHE_EXPIRE
        )
    else:
        response = await factory()

    response_entries = orjson.loads(response)
    return await _get_search_result(
        at_sequence_id=at_sequence_id, response_entries=response_entries
    )


async def _get_search_result(
    *,
    at_sequence_id: SequenceId | None,
    response_entries: list[NominatimPlace],
) -> list[SearchResult]:
    """Convert nominatim places into search results."""
    typed_ids: list[TypedElementId] = []
    entries: list[NominatimPlace] = []
    for entry in response_entries:
        # some results are abstract and have no osm_type/osm_id
        osm_type = entry.get('osm_type')
        osm_id = entry.get('osm_id')
        if osm_type is not None and osm_id is not None:
            typed_ids.append(typed_element_id(osm_type, osm_id))
            entries.append(entry)

    # fetch elements in the order of entries
    type_id_map: dict[TypedElementId, Element] = {
        e['typed_id']: e
        for e in await ElementQuery.get_by_refs(
            typed_ids,
            at_sequence_id=at_sequence_id,
            limit=len(typed_ids),
        )
    }

    # not all elements may be found in the database
    elements = [type_id_map.get(typed_id) for typed_id in typed_ids]
    result: list[SearchResult] = []

    for entry, element, icon, prefix in zip(
        entries,
        elements,
        features_icons(elements),
        features_prefixes(elements),
        strict=True,
    ):
        if (
            element is None  #
            or not element['visible']
            or prefix is None
        ):
            continue

        bbox = entry['boundingbox']
        miny = float(bbox[0])
        maxy = float(bbox[1])
        minx = float(bbox[2])
        maxx = float(bbox[3])
        bounds = minx, miny, maxx, maxy

        lon = (minx + maxx) / 2
        lat = (miny + maxy) / 2

        result.append(
            SearchResult(
                element=element,
                rank=entry['place_rank'],
                importance=entry['importance'],
                icon=icon,
                prefix=prefix,
                display_name=entry['display_name'],
                point=Point(lon, lat),
                bounds=bounds,
            )
        )

    return result
