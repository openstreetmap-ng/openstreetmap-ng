import json
import logging
import pathlib
import tomllib

import cython

from app.config import CONFIG_DIR
from app.models.element_type import ElementType


@cython.cfunc
def _get_config() -> dict[str, dict[str, str]]:
    """
    Get the feature icon configuration.

    Generic icons are stored under the value '*'.
    """
    return tomllib.loads(pathlib.Path(CONFIG_DIR / 'feature_icons.toml').read_text())


@cython.cfunc
def _get_popular_stats() -> dict[str, dict[str, int]]:
    """
    Get the popularity data of the feature icons.

    The popularity is a simple number of elements with the given tag.
    """
    return json.loads(pathlib.Path(CONFIG_DIR / 'feature_icons_popular.json').read_bytes())


@cython.cfunc
def _check_config():
    _num_icons = 0

    # raise an exception if any of the icons are missing
    for key_config in _config.values():
        for icon_or_type_config in key_config.values():
            icon_or_type_config: str | dict

            icons = (icon_or_type_config,) if isinstance(icon_or_type_config, str) else icon_or_type_config.values()
            _num_icons += len(icons)

            for icon in icons:
                path = pathlib.Path('app/static/img/element/' + icon)
                if not path.is_file():
                    raise FileNotFoundError(path)

    logging.info('Loaded %d feature icons', _num_icons)


# format:
# _config[tag_key][tag_value] = icon
# _config[tag_key.type][tag_value] = icon
_config = _get_config()
_config_keys = frozenset(k.split('.', 1)[0] for k in _config)
_popular_stats = _get_popular_stats()
_check_config()


def feature_icon(type: ElementType, tags: dict[str, str]) -> tuple[str, str] | None:
    """
    Get the filename and title of the icon for an element.

    Returns None if no appropriate icon is found.

    >>> feature_icon('way', {'aeroway': 'terminal'})
    'aeroway_terminal.webp', 'aeroway=terminal'
    """
    matched_keys = _config_keys.intersection(tags)
    if not matched_keys:
        return None

    result: list[tuple[int, str, str]] | None = None

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
                    result = [(popularity, icon, title)]
                else:
                    result.append((popularity, icon, title))

        # pick the least popular tagging icon
        if result:
            return min(result)[1:]

    return None
