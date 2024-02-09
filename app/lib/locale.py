import logging
import pathlib
import re
from collections.abc import Sequence

import cython
import orjson

from app.config import DEFAULT_LANGUAGE, LOCALE_DIR, TEST_ENV
from app.limits import LANGUAGE_CODE_MAX_LENGTH
from app.models.locale_name import LocaleName

_non_alpha_re = re.compile(r'[^a-z]+')


@cython.cfunc
def _get_i18next_locale_map() -> dict[str, str]:
    return orjson.loads(pathlib.Path(LOCALE_DIR / 'i18next_map.json').read_bytes())


@cython.cfunc
def _get_locales_names() -> tuple[LocaleName, ...]:
    data = orjson.loads(pathlib.Path(LOCALE_DIR / 'names.json').read_bytes())
    return tuple(sorted((LocaleName(**d) for d in data), key=lambda v: v.code))


@cython.cfunc
def _normalize(code: str) -> str:
    code = code.casefold()  # lowercase
    code = _non_alpha_re.sub('-', code)  # remove non-alpha characters
    code = code.strip('-')  # remove leading and trailing dashes
    return code


_i18next_map = _get_i18next_locale_map()

_locales = frozenset(_i18next_map.keys())
_locales_normalized_map = {_normalize(k): k for k in _locales}
logging.info('Loaded %d locales', len(_locales))

# check that default locale exists
if DEFAULT_LANGUAGE not in _locales:
    raise RuntimeError(f'Default locale {DEFAULT_LANGUAGE=!r} not found in locales')

# check that all language codes are short enough
for code in _locales:
    if len(code) > LANGUAGE_CODE_MAX_LENGTH:
        raise RuntimeError(f'Language code {code=!r} is too long ({len(code)=} > {LANGUAGE_CODE_MAX_LENGTH=})')

_locales_names = _get_locales_names()
logging.info('Loaded %d locales names', len(_locales_names))


def map_i18next_files(locales: Sequence[str]) -> Sequence[str]:
    """
    Map the locales to i18next files.

    >>> map_i18next_files(['en', 'pl'])
    ['en-c39c7633ceb0ce46.js', 'pl-e4c39a792074d67c.js']
    """

    # force reload map in test environment
    if TEST_ENV:
        global _i18next_map
        _i18next_map = _get_i18next_locale_map()

    return tuple(_i18next_map[code] for code in locales)


def is_valid_locale(code: str) -> bool:
    """
    Check if the locale code is valid.

    >>> is_valid_locale('en')
    True
    >>> is_valid_locale('NonExistent')
    False
    """

    return code in _locales


def normalize_locale(code: str, *, raise_on_not_found: bool = False) -> str:
    """
    Normalize locale code case.

    >>> normalize_locale('EN')
    'en'
    >>> normalize_locale('NonExistent', raise_on_not_found=True)
    KeyError: 'NonExistent'
    """

    # skip if already normalized
    if code in _locales:
        return code

    normalized = _normalize(code)

    if raise_on_not_found:
        return _locales_normalized_map[normalized]
    else:
        return _locales_normalized_map.get(normalized, code)


def get_all_installed_locales() -> frozenset[str]:
    """
    Get all installed locales.

    >>> get_all_installed_locales()
    frozenset({'en', 'pl', ...})
    """

    return _locales


def get_all_locales_names() -> Sequence[LocaleName]:
    """
    Get all locales names sorted by code.

    >>> get_all_locales_names()
    [LocaleName(code='pl', english='Polish', native='Polski'), ...]
    """

    return _locales_names
