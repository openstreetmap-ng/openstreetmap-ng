import cython

from app.lib.translation import t, translation_languages
from app.limits import FEATURE_PREFIX_TAGS_LIMIT
from app.models.element_type import ElementType


@cython.cfunc
def _feature_prefix_administrative(tags: dict[str, str]) -> str:
    """
    Returns a human readable prefix for an administrative boundary based on its tags.

    >>> _feature_prefix_administrative({'admin_level': '2'})
    'Country Boundary'
    """

    if (admin_level_str := tags.get('admin_level')) and len(admin_level_str) <= 2:
        admin_level: cython.int

        try:
            admin_level = int(admin_level_str)
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


def feature_prefix(type: ElementType, tags: dict[str, str]) -> str:
    """
    Returns a human readable prefix for a feature based on its type and tags.

    >>> feature_prefix(ElementType.node, {'amenity': 'restaurant'})
    'Restaurant'
    """

    if tags.get('boundary') == 'administrative':
        return _feature_prefix_administrative(tags)

    # tag specific translations
    if len(tags) <= FEATURE_PREFIX_TAGS_LIMIT:
        # read method once for performance
        _t = t

        # key+value matches
        for key, value in tags.items():
            message = f'geocoder.search_osm_nominatim.prefix.{key}.{value}'
            if (translated := _t(message)) != message:
                return translated

        # key matches
        for key, value in tags.items():
            if value != 'yes':
                continue
            message = f'geocoder.search_osm_nominatim.prefix.{key}.yes'
            if _t(message) != message:
                return value.capitalize().replace('_', ' ')

    # type generic translations
    if type == ElementType.node:
        return t('javascripts.query.node')
    elif type == ElementType.way:
        return t('javascripts.query.way')
    elif type == ElementType.relation:
        return t('javascripts.query.relation')
    else:
        raise NotImplementedError(f'Unsupported element type {type!r}')


def feature_name(id: int, tags: dict[str, str]) -> str:
    """
    Returns a human readable name for a feature based on its id and tags.

    >>> feature_name(123, {'name': 'Foo'})
    'Foo'
    """

    # small optimization, most elements don't have tags
    if not tags:
        return f'#{id}'

    for locale in translation_languages():
        if name := tags.get(f'name:{locale}'):
            return name

    if name := tags.get('name'):
        return name
    if ref := tags.get('ref'):
        return ref
    if house_name := tags.get('addr:housename'):
        return house_name
    if (house_number := tags.get('addr:housenumber')) and (street := tags.get('addr:street')):
        return f'{house_number} {street}'

    return f'#{id}'
