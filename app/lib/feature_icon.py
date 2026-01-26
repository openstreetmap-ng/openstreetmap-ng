import logging
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

import cython
import orjson

from app.models.db.element import Element, ElementInit
from speedup import element_type


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
    total_icons: cython.size_t = 0
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

_CONFIG_GENERIC: dict[str, dict[str, str]] = {}
_CONFIG_NODE: dict[str, dict[str, str]] = {}
_CONFIG_WAY: dict[str, dict[str, str]] = {}
_CONFIG_RELATION: dict[str, dict[str, str]] = {}
for _config_key, _values_icons_map in _CONFIG.items():
    if '.' not in _config_key:
        _CONFIG_GENERIC[_config_key] = _values_icons_map
        continue

    _key, _type = _config_key.split('.', 1)
    if _type == 'node':
        _CONFIG_NODE[_key] = _values_icons_map
    elif _type == 'way':
        _CONFIG_WAY[_key] = _values_icons_map
    elif _type == 'relation':
        _CONFIG_RELATION[_key] = _values_icons_map
    else:
        raise NotImplementedError(f'Unsupported element type {_type!r}')

_POPULAR_GENERIC: dict[str, dict[str, int]] = {}
_POPULAR_NODE: dict[str, dict[str, int]] = {}
_POPULAR_WAY: dict[str, dict[str, int]] = {}
_POPULAR_RELATION: dict[str, dict[str, int]] = {}
for _config_key, _values_popularity_map in _POPULAR_STATS.items():
    if '.' not in _config_key:
        _POPULAR_GENERIC[_config_key] = _values_popularity_map
        continue

    _key, _type = _config_key.split('.', 1)
    if _type == 'node':
        _POPULAR_NODE[_key] = _values_popularity_map
    elif _type == 'way':
        _POPULAR_WAY[_key] = _values_popularity_map
    elif _type == 'relation':
        _POPULAR_RELATION[_key] = _values_popularity_map
    else:
        raise NotImplementedError(f'Unsupported element type {_type!r}')


def features_icons(elements: Iterable[Element | ElementInit | None]):
    """
    Get the icons filenames and titles for the given elements.

    If no appropriate icon is found, returns None for that element.

    >>> features_icons(...)
    (('aeroway_terminal.webp', 'aeroway=terminal'), ...)
    """
    return [_feature_icon(e) if e is not None else None for e in elements]


@cython.cfunc
def _feature_icon(
    element: Element | ElementInit,
    /,
    *,
    _CONFIG_KEYS=_CONFIG_KEYS,
    _CONFIG_GENERIC=_CONFIG_GENERIC,
    _POPULAR_GENERIC=_POPULAR_GENERIC,
    _CONFIG_NODE=_CONFIG_NODE,
    _CONFIG_RELATION=_CONFIG_RELATION,
    _CONFIG_WAY=_CONFIG_WAY,
    _POPULAR_NODE=_POPULAR_NODE,
    _POPULAR_RELATION=_POPULAR_RELATION,
    _POPULAR_WAY=_POPULAR_WAY,
    _EMPTY: dict = {},
):
    tags = element['tags']
    if not tags:
        return None

    config_typed: dict[str, dict[str, str]] | None = None
    popular_typed: dict[str, dict[str, int]] | None = None
    best_specific: FeatureIcon | None = None
    best_generic: FeatureIcon | None = None

    for key, value in tags.items():
        if key not in _CONFIG_KEYS:
            continue

        if config_typed is None:
            type = element_type(element['typed_id'])
            if type == 'node':
                config_typed = _CONFIG_NODE
                popular_typed = _POPULAR_NODE
            elif type == 'way':
                config_typed = _CONFIG_WAY
                popular_typed = _POPULAR_WAY
            elif type == 'relation':
                config_typed = _CONFIG_RELATION
                popular_typed = _POPULAR_RELATION
            else:
                raise NotImplementedError(
                    f'Unsupported element type {type!r} in typed id {element["typed_id"]}'
                )

        assert config_typed is not None
        assert popular_typed is not None

        # Prefer value-specific icons first.
        values_icons_map = config_typed.get(key)
        if (
            values_icons_map is not None
            and (icon := values_icons_map.get(value)) is not None
        ):
            popularity = popular_typed.get(key, _EMPTY).get(value, 0)
            if best_specific is None or popularity < best_specific.popularity:
                best_specific = FeatureIcon(popularity, icon, f'{key}={value}')
                if popularity == 0:
                    return best_specific
            continue

        values_icons_map = _CONFIG_GENERIC.get(key)
        if (
            values_icons_map is not None
            and (icon := values_icons_map.get(value)) is not None
        ):
            popularity = _POPULAR_GENERIC.get(key, _EMPTY).get(value, 0)
            if best_specific is None or popularity < best_specific.popularity:
                best_specific = FeatureIcon(popularity, icon, f'{key}={value}')
                if popularity == 0:
                    return best_specific
            continue

        # Generic fallback: only relevant if no specific match was found anywhere.
        if best_specific is not None:
            continue

        values_icons_map = config_typed.get(key)
        if (
            values_icons_map is not None
            and (icon := values_icons_map.get('*')) is not None
        ):
            popularity = popular_typed.get(key, _EMPTY).get('*', 0)
            if best_generic is None or popularity < best_generic.popularity:
                best_generic = FeatureIcon(popularity, icon, key)
            continue

        values_icons_map = _CONFIG_GENERIC.get(key)
        if (
            values_icons_map is not None
            and (icon := values_icons_map.get('*')) is not None
        ):
            popularity = _POPULAR_GENERIC.get(key, _EMPTY).get('*', 0)
            if best_generic is None or popularity < best_generic.popularity:
                best_generic = FeatureIcon(popularity, icon, key)

    return best_specific if best_specific is not None else best_generic
