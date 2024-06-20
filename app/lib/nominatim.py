import logging
from collections.abc import Sequence
from urllib.parse import urlencode

import numpy as np
from httpx import HTTPError
from shapely import Point, Polygon, STRtree, box, get_coordinates

from app.config import NOMINATIM_URL
from app.lib.feature_name import features_prefixes
from app.lib.translation import primary_translation_language
from app.limits import (
    NOMINATIM_CACHE_LONG_EXPIRE,
    NOMINATIM_CACHE_SHORT_EXPIRE,
    NOMINATIM_HTTP_LONG_TIMEOUT,
    NOMINATIM_HTTP_SHORT_TIMEOUT,
    SEARCH_RESULTS_LIMIT,
)
from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.models.element_type import ElementType
from app.models.nominatim_result import NominatimResult
from app.queries.element_query import ElementQuery
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
            cache = await CacheService.get(
                path,
                context=_cache_context,
                factory=factory,
                ttl=NOMINATIM_CACHE_LONG_EXPIRE,
            )
            return JSON_DECODE(cache.value)['display_name']
        except HTTPError:
            logging.warning('Nominatim reverse geocoding failed', exc_info=True)
            # always succeed, return coordinates as a fallback
            return f'{y:.5f}, {x:.5f}'

    # TODO: use single method
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
                'limit': SEARCH_RESULTS_LIMIT,
                **({'viewbox': ','.join(f'{x:.7f}' for x in bounds.bounds)} if (bounds is not None) else {}),
                'accept-language': primary_translation_language(),
            }
        )

        async def factory() -> bytes:
            logging.debug('Nominatim search cache miss for path %r', path)
            r = await HTTP.get(NOMINATIM_URL + path, timeout=NOMINATIM_HTTP_LONG_TIMEOUT.total_seconds())
            r.raise_for_status()
            return r.content

        cache = await CacheService.get(
            path,
            context=_cache_context,
            factory=factory,
            hash_key=True,
            ttl=NOMINATIM_CACHE_SHORT_EXPIRE,
        )
        result: dict = JSON_DECODE(cache.value)[0]

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
    async def search_elements(
        *,
        q: str,
        bounds: Polygon | None = None,
        at_sequence_id: int | None,
        limit: int,
    ) -> Sequence[NominatimResult]:
        """
        Search for a location by name.

        Returns a sequence of NominatimResult.
        """
        path = '/search?' + urlencode(
            {
                'format': 'jsonv2',
                'q': q,
                'limit': limit,
                **({'viewbox': ','.join(f'{x:.7f}' for x in bounds.bounds)} if (bounds is not None) else {}),
                'accept-language': primary_translation_language(),
            }
        )

        async def factory() -> bytes:
            logging.debug('Nominatim search cache miss for path %r', path)
            r = await HTTP.get(NOMINATIM_URL + path, timeout=NOMINATIM_HTTP_LONG_TIMEOUT.total_seconds())
            r.raise_for_status()
            return r.content

        cache = await CacheService.get(
            path,
            context=_cache_context,
            factory=factory,
            hash_key=True,
            ttl=NOMINATIM_CACHE_SHORT_EXPIRE,
        )

        refs: list[ElementRef] = []
        entries: list[dict] = []
        for entry in JSON_DECODE(cache.value):
            # some results are abstract and have no osm_type/osm_id
            osm_type = entry.get('osm_type')
            osm_id = entry.get('osm_id')
            if (osm_type is None) or (osm_id is None):
                continue

            ref = ElementRef(osm_type, osm_id)
            refs.append(ref)
            entries.append(entry)

        elements = await ElementQuery.get_by_refs(refs, at_sequence_id=at_sequence_id, limit=len(refs))

        # reorder elements to match the order of entries
        ref_element_map: dict[ElementRef, Element] = {ElementRef(e.type, e.id): e for e in elements}
        elements = tuple(ref_element_map.get(ref) for ref in refs)

        prefixes = features_prefixes(elements)
        result = []
        for entry, element, prefix in zip(entries, elements, prefixes, strict=True):
            # skip non-existing elements
            if element is None or not element.visible:
                continue

            bbox = entry['boundingbox']
            miny = float(bbox[0])
            maxy = float(bbox[1])
            minx = float(bbox[2])
            maxx = float(bbox[3])
            geometry: Polygon = box(minx, miny, maxx, maxy)
            result.append(
                NominatimResult(
                    element=element,
                    rank=entry['place_rank'],
                    importance=entry['importance'],
                    prefix=prefix,
                    display_name=entry['display_name'],
                    point=geometry.representative_point(),
                    bounds=geometry,
                )
            )
        return result

    @staticmethod
    def deduplicate_similar_results(results: Sequence[NominatimResult]) -> Sequence[NominatimResult]:
        """
        Deduplicate similar results.
        """
        # TODO: remove later
        results = list(results)
        print(results)

        # Deduplicate by type and id
        seen_type_id: set[tuple[ElementType, int]] = set()
        dedup1: list[NominatimResult] = []
        geoms: list[Point] = []
        for result in results:
            element = result.element
            type_id = (element.type, element.id)
            if type_id in seen_type_id:
                continue
            seen_type_id.add(type_id)
            dedup1.append(result)
            geoms.append(result.point)

        if len(dedup1) <= 1:
            return dedup1

        # Deduplicate by location and name
        tree = STRtree(geoms)
        nearby_all: np.ndarray = tree.query(geoms, 'dwithin', 0.001)
        nearby_all = np.sort(nearby_all.T, axis=1)
        nearby_all = np.unique(nearby_all, axis=0)
        mask = np.ones(len(geoms), dtype=bool)
        for i1, i2 in nearby_all:
            if i1 >= i2 or not mask[i1]:
                continue
            name1 = dedup1[i1].display_name
            name2 = dedup1[i2].display_name
            if name1 != name2:
                continue
            mask[i2] = False

        return tuple(dedup1[i] for i in np.nonzero(mask)[0])
