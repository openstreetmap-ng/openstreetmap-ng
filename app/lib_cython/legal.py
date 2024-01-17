import logging
import pathlib
from functools import cache

import cython
import yaml

from app.config import LEGAL_DIR

if cython.compiled:
    print(f'{__name__}: 🐇 compiled')


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

    with pathlib.Path(LEGAL_DIR / f'{locale}.yml').open() as f:
        return yaml.safe_load(f)
