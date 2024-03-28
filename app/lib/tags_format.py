from collections.abc import Callable

import cython

from app.lib.tags_formatter.color import configure_color_format
from app.lib.tags_formatter.comment import configure_comment_format
from app.lib.tags_formatter.email import configure_email_format
from app.lib.tags_formatter.osm_wiki import tags_format_osm_wiki
from app.lib.tags_formatter.phone import configure_phone_format
from app.lib.tags_formatter.url import configure_url_format
from app.lib.tags_formatter.wikidata import configure_wikidata_format
from app.lib.tags_formatter.wikimedia_commons import configure_wikimedia_commons_format
from app.lib.tags_formatter.wikipedia import configure_wikipedia_format
from app.models.tag_format import TagFormatCollection

# TODO: 0.7 official reserved tag characters


def tags_format(tags: dict[str, str]) -> dict[str, TagFormatCollection]:
    """
    Format tags for displaying on the website (colors, urls, etc.).

    Returns a mapping of tag keys to TagFormatCollection.
    """
    max_key_parts: cython.int = 5
    max_values: cython.int = 8

    result_init = [(key, TagFormatCollection(key, value)) for key, value in tags.items()]
    result_init.sort()
    result = dict(result_init)
    result_values = result.values()

    for tag in result_values:
        # split a:b:c keys into ['a', 'b', 'c']
        key_parts = tag.key.value.split(':', maxsplit=max_key_parts)

        # skip unexpectedly long sequences
        if len(key_parts) > max_key_parts:
            continue

        supported_key_parts = _method_keys.intersection(key_parts)
        supported_key_part = next(iter(supported_key_parts), None)
        if supported_key_part is None:
            continue

        # split a;b;c values into ['a', 'b', 'c']
        values = tag.values[0].value.split(';', maxsplit=max_values)

        # skip unexpectedly long sequences
        if len(values) > max_values:
            continue

        _method_map[supported_key_part](tag, key_parts, values)

    tags_format_osm_wiki(result_values)

    # TODO: remove after testing
    # result['colour'] = TagStyleCollection('colour', 'red;blue')
    # result['email'] = TagStyleCollection('email', '1@example.com;2@example.com')
    # result['something:email'] = TagStyleCollection('something:email', '1@example.com;2@example.com')
    # result['phone'] = TagStyleCollection('phone', '+1-234-567-8901')
    # result['amenity'] = TagStyleCollection('amenity', 'bench')

    return result


_method_map: dict[str, Callable[[TagFormatCollection, list[str], list[str]], None]] = {}
configure_color_format(_method_map)
configure_comment_format(_method_map)
configure_email_format(_method_map)
configure_phone_format(_method_map)
configure_url_format(_method_map)
configure_wikipedia_format(_method_map)
configure_wikidata_format(_method_map)
configure_wikimedia_commons_format(_method_map)

_method_keys = frozenset(_method_map.keys())
