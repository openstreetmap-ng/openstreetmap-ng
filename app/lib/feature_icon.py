import pathlib
import tomllib

import cython

from app.config import CONFIG_DIR
from app.models.db.element import Element


@cython.cfunc
def _get_config() -> dict[str, dict[str, str | dict[str, str]]]:
    """
    Get the feature icon configuration.

    Generic icons are stored under the value '*'.
    """
    return tomllib.loads(pathlib.Path(CONFIG_DIR / 'feature_icon.toml').read_text())


# _config[tag_key][tag_value] = icon
# _config[tag_key][type][tag_value] = icon
_config = _get_config()
_config_keys = frozenset(_config)


# raise an exception if any of the icon files are missing
for key_config in _config.values():
    for icon_or_type_config in key_config.values():
        icon_or_type_config: str | dict

        icons = (icon_or_type_config,) if isinstance(icon_or_type_config, str) else icon_or_type_config.values()

        for icon in icons:
            path = pathlib.Path('app/static/img/element/' + icon)
            if not path.is_file():
                raise FileNotFoundError(path)


# TODO: deleted objects use previous tagging
def feature_icon(element: Element) -> tuple[str, str] | tuple[None, None]:
    """
    Get the filename and title of the icon for an element.

    >>> element_icon({'aeroway': 'terminal'})
    'aeroway_terminal.webp', 'aeroway=terminal'

    >>> element_icon({'source': 'bing'})
    None, None
    """

    # read property once for performance
    tags = element.tags

    # small optimization, majority of the elements don't have any tags
    if not tags:
        return None, None

    element_type = element.type
    matched_keys = _config_keys.intersection(tags)

    # 1. check value-specific configuration
    for key in matched_keys:
        key_value: str = tags[key]
        key_config: dict[str, str | dict[str, str]] = _config[key]
        type_config: dict[str, str] | None = key_config.get(element_type)

        # prefer type-specific configuration
        if (type_config is not None) and (icon := type_config.get(key_value)) is not None:
            return icon, f'{key}={key_value}'

        if (icon := key_config.get(key_value)) is not None and isinstance(icon, str):
            return icon, f'{key}={key_value}'

    # 2. check key-specific configuration (generic)
    for key in matched_keys:
        key_config: dict[str, str | dict[str, str]] = _config[key]
        type_config: dict[str, str] | None = key_config.get(element_type)

        # prefer type-specific configuration
        if (type_config is not None) and (icon := type_config.get('*')) is not None:
            return icon, key

        if (icon := key_config.get('*')) is not None:
            return icon, key

    return None, None
