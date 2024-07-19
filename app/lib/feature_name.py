from app.lib.translation import translation_locales


# TODO: batch, features_names
def feature_name(tags: dict[str, str]) -> str | None:
    """
    Returns a human readable name for a feature.

    >>> feature_name({'name': 'Foo'})
    'Foo'
    """
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
