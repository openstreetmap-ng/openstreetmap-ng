from collections.abc import Iterable

import cython

from app.lib.translation import translation_locales
from app.models.db.element import Element


def features_names(elements: Iterable[Element]) -> tuple[str | None, ...]:
    """
    Returns human-readable names for features.

    >>> features_names(...)
    ('Foo', ...)
    """
    return tuple(_feature_name(e.tags) for e in elements)


@cython.cfunc
def _feature_name(tags: dict[str, str]):
    if not tags:
        return None
    for locale in translation_locales():
        if name := tags.get(f'name:{locale}'):
            return name

    if name := tags.get('name'):
        return name
    if ref := tags.get('ref'):
        return ref
    if house_name := tags.get('addr:housename'):
        return house_name
    if house_number := tags.get('addr:housenumber'):
        if street := tags.get('addr:street'):
            return f'{house_number} {street}'
        if place := tags.get('addr:place'):
            return f'{house_number} {place}'

    return None
