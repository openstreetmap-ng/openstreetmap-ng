import json
import logging
import re
from collections.abc import Sequence
from pathlib import Path

import cython

from app.config import DEFAULT_LANGUAGE, TEST_ENV
from app.limits import LANGUAGE_CODE_MAX_LENGTH
from app.models.locale_name import LocaleName

_non_alpha_re = re.compile(r'[^a-z]+')


@cython.cfunc
def _get_i18next_locale_map() -> dict[str, str]:
    return json.loads(Path('config/locale/i18next/map.json').read_bytes())


@cython.cfunc
def _get_locales_names() -> tuple[LocaleName, ...]:
    names = json.loads(Path('config/locale/names.json').read_bytes())
    structured = (LocaleName(**d) for d in names)
    return tuple(sorted(structured, key=lambda v: v.code))


@cython.cfunc
def _normalize(code: str) -> str:
    code = code.casefold()  # lowercase
    code = _non_alpha_re.sub('-', code)  # remove non-alpha characters
    code = code.strip('-')  # remove leading and trailing dashes
    return code


_i18next_map = _get_i18next_locale_map()
LOCALES = frozenset(_i18next_map.keys())
_locales_normalized_map = {_normalize(k): k for k in LOCALES}
LOCALES_NAMES = _get_locales_names()
logging.info('Loaded %d locales and %d locales names', len(LOCALES), len(LOCALES_NAMES))

# check that default locale exists
if DEFAULT_LANGUAGE not in LOCALES:
    raise ValueError(f'Default locale {DEFAULT_LANGUAGE!r} not found in locales')

# check that all language codes are short enough
for code in LOCALES:
    if len(code) > LANGUAGE_CODE_MAX_LENGTH:
        raise ValueError(f'Language code {code!r} is too long ({len(code)} > {LANGUAGE_CODE_MAX_LENGTH})')


def map_i18next_files(locales: Sequence[str]) -> tuple[str, ...]:
    """
    Map the locales to i18next files.

    Returns at most two files: primary and fallback locale.

    >>> map_i18next_files(['pl', 'de', 'en'])
    ['pl-e4c39a792074d67c.js', 'en-c39c7633ceb0ce46.js']
    """
    # force reload map in test environment
    if TEST_ENV:
        global _i18next_map
        _i18next_map = _get_i18next_locale_map()

    # i18next supports only primary+fallback locale
    primary_locale = locales[0]
    primary_file = _i18next_map[primary_locale]
    if len(locales) == 1:
        return (primary_file,)
    fallback_locale = locales[-1]
    fallback_file = _i18next_map[fallback_locale]
    return (primary_file, fallback_file)


def is_valid_locale(code: str) -> bool:
    """
    Check if the locale code is valid.

    >>> is_valid_locale('en')
    True
    >>> is_valid_locale('NonExistent')
    False
    """
    return code in LOCALES


def normalize_locale(code: str) -> str | None:
    """
    Normalize locale code case.

    Returns None if the locale is not found.

    >>> normalize_locale('EN')
    'en'
    >>> normalize_locale('NonExistent')
    None
    """
    # skip if already normalized
    if code in LOCALES:
        return code
    return _locales_normalized_map.get(_normalize(code))
