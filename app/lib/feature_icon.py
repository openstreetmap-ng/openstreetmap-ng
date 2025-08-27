import logging
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

import cython
import orjson

from app.models.db.element import Element, ElementInit
from speedup.element_type import split_typed_element_id


class FeatureIcon(NamedTuple):
    popularity: int  # first element defines sort order
    filename: str
    title: str


@cython.cfunc
def _get_config() -> dict[str, dict[str, str]]:
    """
    Load the feature icon configuration.

    Configuration schema:
    - [key][value] = icon
    - [key.type][value] = icon

    Generic icons are stored under the '*' value:
    - [key][*] = icon
    """
    return tomllib.loads(Path('config/feature_icons.toml').read_text())


@cython.cfunc
def _get_popular_stats() -> dict[str, dict[str, int]]:
    """Load the feature icon popularity data."""
    return orjson.loads(Path('config/feature_icons_popular.json').read_bytes())


@cython.cfunc
def _check_config():
    # ensure all icons are present
    total_icons: cython.Py_ssize_t = 0
    for key_config in _CONFIG.values():
        for icon in key_config.values():
            with Path('app/static/img/element', icon).open('rb'):
                pass
        total_icons += len(key_config)
    logging.info('Loaded %d feature icons', total_icons)


_CONFIG = _get_config()
_CONFIG_KEYS = frozenset(k.split('.', 1)[0] for k in _CONFIG)
_POPULAR_STATS = _get_popular_stats()
_check_config()


def features_icons(
    elements: Iterable[Element | ElementInit | None],
) -> list[FeatureIcon | None]:
    """
    Get the icons filenames and titles for the given elements.

    If no appropriate icon is found, returns None for that element.

    >>> features_icons(...)
    (('aeroway_terminal.webp', 'aeroway=terminal'), ...)
    """
    return [_feature_icon(e) if e is not None else None for e in elements]


@cython.cfunc
def _feature_icon(element: Element | ElementInit):
    tags = element['tags']
    if not tags:
        return None

    matched_keys = _CONFIG_KEYS.intersection(tags)
    if not matched_keys:
        return None

    type = split_typed_element_id(element['typed_id'])[0]
    result: list[FeatureIcon] | None = None
    specific: cython.bint

    # prefer value-specific icons first
    for specific in (True, False):
        for key in matched_keys:
            value = tags[key] if specific else '*'

            # prefer type-specific icons first
            for config_key in (f'{key}.{type}', key):
                values_icons_map = _CONFIG.get(config_key)
                if values_icons_map is None:
                    continue

                icon = values_icons_map.get(value)
                if icon is None:
                    continue

                popularity = _POPULAR_STATS.get(config_key, {}).get(value, 0)
                title = f'{key}={value}' if specific else key

                if result is None:
                    result = [FeatureIcon(popularity, icon, title)]
                else:
                    result.append(FeatureIcon(popularity, icon, title))

        # pick the least popular tagging icon
        if result:
            return min(result)

    return None
