import logging
import pathlib
from functools import cache

import yaml

from app.config import LEGAL_DIR


@cache
def get_legal(locale: str) -> dict:
    """
    Get legal information for a locale.

    >>> get_legal('GB')
    {'intro': '...', 'next_with_decline': '...', ...}
    >>> get_legal('NonExistent')
    FileNotFoundError: [Errno 2] No such file or directory: 'config/legal/NonExistent.yml'
    """

    logging.info('Loading legal for %s', locale)
    path = LEGAL_DIR / f'{locale}.yml'
    return yaml.load(path.read_bytes(), yaml.CSafeLoader)
