import logging
from typing import Any

import cython
from httpx import Timeout
from shapely import Point, get_coordinates

from app.config import OVERPASS_INTERPRETER_URL
from app.format import FormatLeaflet
from app.lib.feature_icon import features_icons
from app.lib.feature_name import features_names
from app.lib.feature_prefix import features_prefixes
from app.lib.query_features import QueryFeatureResult
from app.limits import OVERPASS_CACHE_EXPIRE, QUERY_FEATURES_RESULTS_LIMIT
from app.models.db.element import Element
from app.models.element import ElementId, ElementType
from app.services.cache_service import CacheContext, CacheService
from app.utils import HTTP, JSON_DECODE

_cache_context = CacheContext('Overpass')


class OverpassQuery:
    @staticmethod
    async def nearby_elements(point: Point, radius_meters: float) -> list[QueryFeatureResult]:
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
        elements_data: list[dict[str, Any]] = JSON_DECODE(cache.value)['elements']  # pyright: ignore[reportInvalidTypeForm]
        elements_data.sort(key=_sort_key)
        type_id_map: dict[tuple[ElementType, ElementId], dict[str, Any]] = {
            (element['type'], element['id']): element  #
            for element in elements_data
        }

        elements_unfiltered: list[Element] = [None] * len(elements_data)  # pyright: ignore[reportAssignmentType]
        i: cython.int
        for i, element in enumerate(elements_data):
            element_type = element['type']
            elements_unfiltered[i] = Element(
                changeset_id=0,
                type=element_type,
                id=element['id'],
                version=0,
                visible=True,
                tags=element.get('tags', {}),
                point=Point(element['lon'], element['lat']) if element_type == 'node' else None,
            )

        elements = FormatLeaflet.filter_tags_interesting(elements_unfiltered)[:QUERY_FEATURES_RESULTS_LIMIT]
        icons = features_icons(elements)
        names = features_names(elements)
        prefixes = features_prefixes(elements)

        result: list[QueryFeatureResult] = [None] * len(elements)  # pyright: ignore[reportAssignmentType]
        i: cython.int
        for i, element, icon, name, prefix in zip(range(len(elements)), elements, icons, names, prefixes, strict=True):
            element_type = element.type
            element_data = type_id_map[(element_type, element.id)]
            if element_type == 'node':
                element_point: Point = element.point  # pyright: ignore[reportAssignmentType]
                geoms = (element_point,)
            elif element_type == 'way':
                geoms = (
                    tuple(
                        (point['lon'], point['lat'])  #
                        for point in element_data['geometry']
                    ),
                )
            elif element_type == 'relation':
                members = element_data['members']
                geoms_list: list[Point | tuple[tuple[float, float], ...]] = []
                for member in members:
                    member_type: ElementType = member['type']
                    member_data = type_id_map.get((member_type, member['ref']))
                    if member_data is None:
                        continue
                    if member_type == 'node':
                        geoms_list.append(Point(member_data['lon'], member_data['lat']))
                    elif member_type == 'way':
                        geoms_list.append(
                            tuple(
                                (point['lon'], point['lat'])  #
                                for point in member_data['geometry']
                            )
                        )
                geoms = geoms_list
            else:
                raise NotImplementedError(f'Unsupported element type {element_type!r}')
            result[i] = QueryFeatureResult(
                element=element,
                icon=icon,
                prefix=prefix,
                display_name=name,
                geoms=geoms,
            )
        return result

    @staticmethod
    async def enclosing_elements(point: Point) -> tuple[Element, ...]:
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
            'out tags bb;'
            'rel(pivot.a);'
            'out tags bb;'
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
        elements: list[dict[str, Any]] = JSON_DECODE(cache.value)['elements']  # pyright: ignore[reportInvalidTypeForm]
        elements.sort(key=_sort_key)
        return tuple(
            Element(
                changeset_id=0,
                type=element['type'],
                id=element['id'],
                version=0,
                visible=True,
                tags=element['tags'],
                point=None,
            )
            for element in elements
        )


@cython.cfunc
def _sort_key(element: dict):
    if element['type'] == 'node':
        return (0, -element['id'])
    bounds: dict = element['bounds']
    minlon: cython.double = bounds['minlon']
    minlat: cython.double = bounds['minlat']
    maxlon: cython.double = bounds['maxlon']
    maxlat: cython.double = bounds['maxlat']
    size = (maxlon - minlon) * (maxlat - minlat)
    return (1, size)
