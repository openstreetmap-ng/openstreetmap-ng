import logging
import pathlib
from types import MappingProxyType

import yaml


def _load_legal() -> dict[str, dict]:
    result = {}

    for p in pathlib.Path('config/legal').iterdir():
        if not p.is_dir():
            continue

        with p.open() as f:
            result[p.name] = yaml.safe_load(f)

    return result


_legals = MappingProxyType(_load_legal())

logging.info('Loaded %d legals', len(_legals))


def get_legal(locale: str) -> dict:
    """
    Get legal information for a locale.

    >>> get_legal('EN')
    {'intro': '...', 'next_with_decline': '...', ...}
    >>> get_legal('NonExistent')
    KeyError: 'NonExistent'
    """

    return _legals[locale]
