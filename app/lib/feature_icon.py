import json
import logging
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

import cython

from app.models.db.element import Element
from app.models.element import ElementType


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
    """
    Load the feature icon popularity data.
    """
    return json.loads(Path('config/feature_icons_popular.json').read_bytes())


@cython.cfunc
def _check_config():
    # ensure all icons are present
    total_icons: cython.int = 0
    for key_config in _config.values():
        for icon in key_config.values():
            with Path('app/static/img/element', icon).open('rb'):
                pass
        total_icons += len(key_config)
    logging.info('Loaded %d feature icons', total_icons)


_config = _get_config()
_config_keys = frozenset(k.split('.', 1)[0] for k in _config)
_popular_stats = _get_popular_stats()
_check_config()


def features_icons(elements: Iterable[Element | None]) -> tuple[FeatureIcon | None, ...]:
    """
    Get the icons filenames and titles for the given elements.

    If no appropriate icon is found, returns None for that element.

    >>> features_icons(...)
    (('aeroway_terminal.webp', 'aeroway=terminal'), ...)
    """
    return tuple(_feature_icon(e.type, e.tags) if (e is not None) else None for e in elements)


@cython.cfunc
def _feature_icon(type: ElementType, tags: dict[str, str]):
    if not tags:
        return None
    matched_keys = _config_keys.intersection(tags)
    if not matched_keys:
        return None

    result: list[FeatureIcon] | None = None

    # prefer value-specific icons first
    specific: cython.char
    for specific in (True, False):
        for key in matched_keys:
            value = tags[key] if specific else '*'

            # prefer type-specific icons first
            for config_key in (f'{key}.{type}', key):
                values_icons_map = _config.get(config_key)
                if values_icons_map is None:
                    continue

                icon = values_icons_map.get(value)
                if icon is None:
                    continue

                popularity = _popular_stats.get(config_key, {}).get(value, 0)
                title = f'{key}={value}' if specific else key

                if result is None:
                    result = [FeatureIcon(popularity, icon, title)]
                else:
                    result.append(FeatureIcon(popularity, icon, title))

        # pick the least popular tagging icon
        if result:
            return min(result)

    return None
