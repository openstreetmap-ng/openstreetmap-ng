from collections.abc import Iterable
from typing import overload

import cython

from app.config import FEATURE_PREFIX_TAGS_LIMIT
from app.lib.translation import t
from app.models.db.element import Element, ElementInit
from app.models.element import ElementType
from speedup import element_type


@overload
def features_prefixes(  # type: ignore
    elements: Iterable[Element | ElementInit],
) -> list[str]: ...
@overload
def features_prefixes(
    elements: Iterable[Element | ElementInit | None],
) -> list[str | None]: ...
def features_prefixes(  # type: ignore
    elements: Iterable[Element | ElementInit | None],
):
    """
    Returns a human-readable prefix for a feature based on its type and tags.

    >>> features_prefixes(...)
    ['Restaurant', 'City', ...]
    """
    return [_feature_prefix(e) if e is not None else None for e in elements]


@cython.cfunc
def _feature_prefix(element: Element | ElementInit):
    # tag-specific translations
    tags = element['tags']
    if tags and (r := _feature_prefix_tags(tags)) is not None:
        return r

    # type-generic translations
    type = element_type(element['typed_id'])
    return _feature_prefix_type(type)


@cython.cfunc
def _feature_prefix_tags(tags: dict[str, str]):
    if tags.get('boundary') == 'administrative':
        return _feature_prefix_administrative(tags)

    # skip checking if too many tags
    if len(tags) > FEATURE_PREFIX_TAGS_LIMIT:
        return None

    # read method once for performance
    t_ = t

    # key+value matches
    for key, value in tags.items():
        message = f'geocoder.search_osm_nominatim.prefix.{key}.{value}'
        translated = t_(message)
        if translated != message:
            return translated

    # key matches
    for key, value in tags.items():
        message = f'geocoder.search_osm_nominatim.prefix.{key}.yes'
        translated = t_(message)
        if translated != message:
            # provide automatic feature prefix for unknown tags
            # e.g., amenity=cooking_school -> 'Cooking school'
            return value.capitalize().replace('_', ' ')

    return None


@cython.cfunc
def _feature_prefix_administrative(tags: dict[str, str]):
    """
    Returns a human-readable prefix for an administrative boundary based on its tags.

    >>> _feature_prefix_administrative({'admin_level': '2'})
    'Country Boundary'
    """
    # if admin_level is present, use it to be more specific
    admin_level = tags.get('admin_level')
    if not admin_level:
        return t('geocoder.search_osm_nominatim.prefix.boundary.administrative')

    message = f'geocoder.search_osm_nominatim.admin_levels.level{admin_level}'
    translated = t(message)
    if translated == message:
        return t('geocoder.search_osm_nominatim.prefix.boundary.administrative')

    return translated


@cython.cfunc
def _feature_prefix_type(type: ElementType):
    if type == 'node':
        return t('javascripts.query.node')
    if type == 'way':
        return t('javascripts.query.way')
    if type == 'relation':
        return t('javascripts.query.relation')

    raise NotImplementedError(f'Unsupported element type {type!r}')
