from collections.abc import Iterable
from typing import overload

import cython

from app.lib.translation import t
from app.limits import FEATURE_PREFIX_TAGS_LIMIT
from app.models.db.element import Element
from app.models.element import ElementType


@overload
def features_prefixes(elements: Iterable[Element]) -> tuple[str, ...]: ...


@overload
def features_prefixes(elements: Iterable[Element | None]) -> tuple[str | None, ...]: ...


def features_prefixes(elements: Iterable[Element | None]) -> tuple[str | None, ...]:
    """
    Returns a human-readable prefix for a feature based on its type and tags.

    >>> features_prefixes(...)
    ['Restaurant', 'City', ...]
    """
    return tuple(_feature_prefix(e.type, e.tags) if (e is not None) else None for e in elements)


@cython.cfunc
def _feature_prefix(type: ElementType, tags: dict[str, str]) -> str:
    tags_len: cython.int = len(tags)
    if tags_len > 0:
        if tags.get('boundary') == 'administrative':
            return _feature_prefix_administrative(tags)

        # tag specific translations
        if tags_len <= FEATURE_PREFIX_TAGS_LIMIT:
            # read method once for performance
            _t = t

            # key+value matches
            for key, value in tags.items():
                message = f'geocoder.search_osm_nominatim.prefix.{key}.{value}'
                if (translated := _t(message)) != message:
                    return translated

            # key matches
            for key, value in tags.items():
                message = f'geocoder.search_osm_nominatim.prefix.{key}.yes'
                if _t(message) != message:
                    # provide automatic feature prefix for unknown tags
                    # e.g., amenity=cooking_school -> 'Cooking school'
                    return value.capitalize().replace('_', ' ')

    # type-generic translations
    if type == 'node':
        return t('javascripts.query.node')
    elif type == 'way':
        return t('javascripts.query.way')
    elif type == 'relation':
        return t('javascripts.query.relation')
    else:
        raise NotImplementedError(f'Unsupported element type {type!r}')


@cython.cfunc
def _feature_prefix_administrative(tags: dict[str, str]) -> str:
    """
    Returns a human-readable prefix for an administrative boundary based on its tags.

    >>> _feature_prefix_administrative({'admin_level': '2'})
    'Country Boundary'
    """
    # if admin_level is present, use it to be more specific
    admin_level_value = tags.get('admin_level')
    if admin_level_value and len(admin_level_value) <= 2:
        admin_level: cython.int

        try:
            admin_level = int(admin_level_value)
        except ValueError:
            admin_level = 0

        # hardcoded translations for simple static discovery
        if admin_level == 2:
            message = 'geocoder.search_osm_nominatim.admin_levels.level2'
        elif admin_level == 3:
            message = 'geocoder.search_osm_nominatim.admin_levels.level3'
        elif admin_level == 4:
            message = 'geocoder.search_osm_nominatim.admin_levels.level4'
        elif admin_level == 5:
            message = 'geocoder.search_osm_nominatim.admin_levels.level5'
        elif admin_level == 6:
            message = 'geocoder.search_osm_nominatim.admin_levels.level6'
        elif admin_level == 7:
            message = 'geocoder.search_osm_nominatim.admin_levels.level7'
        elif admin_level == 8:
            message = 'geocoder.search_osm_nominatim.admin_levels.level8'
        elif admin_level == 9:
            message = 'geocoder.search_osm_nominatim.admin_levels.level9'
        elif admin_level == 10:
            message = 'geocoder.search_osm_nominatim.admin_levels.level10'
        elif admin_level == 11:
            message = 'geocoder.search_osm_nominatim.admin_levels.level11'
        else:
            return t('geocoder.search_osm_nominatim.prefix.boundary.administrative')

        if (translated := t(message)) != message:
            return translated

    return t('geocoder.search_osm_nominatim.prefix.boundary.administrative')
