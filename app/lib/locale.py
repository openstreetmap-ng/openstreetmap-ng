import json
import logging
import re
from collections.abc import Sequence
from itertools import chain
from pathlib import Path

import cython

from app.config import DEFAULT_LANGUAGE, TEST_ENV
from app.limits import LANGUAGE_CODE_MAX_LENGTH
from app.models.locale_name import LocaleName

_non_alpha_re = re.compile(r'[^a-z]+')


@cython.cfunc
def _load_locale() -> tuple[dict[str, str], tuple[LocaleName, ...]]:
    i18next_map: dict[str, str] = json.loads(Path('config/locale/i18next/map.json').read_bytes())
    locales_codes_normalized_map = {_normalize(k): k for k in i18next_map}
    raw_names: list[dict[str, str]] = json.loads(Path('config/locale/names.json').read_bytes())
    locale_names_map: dict[str, LocaleName] = {}

    for raw_name in raw_names:
        installed = raw_name['code'] in i18next_map
        locale_name = LocaleName(**raw_name, installed=installed)
        if not locale_name.installed:
            new_code = locales_codes_normalized_map.get(_normalize(locale_name.code))
            if new_code is not None:
                logging.warning('Locale code %r is mistyped, replacing with %r', locale_name.code, new_code)
                locale_name = locale_name._replace(code=new_code)
        locale_names_map[locale_name.code] = locale_name

    # check that default locale exists
    if DEFAULT_LANGUAGE not in i18next_map:
        raise ValueError(f'Default locale {DEFAULT_LANGUAGE!r} was not found in installed locales')
    # check that all language codes are short enough
    for code in chain(i18next_map, locale_names_map):
        if len(code) > LANGUAGE_CODE_MAX_LENGTH:
            raise ValueError(f'Locale code {code!r} is too long ({len(code)} > {LANGUAGE_CODE_MAX_LENGTH})')

    not_found_codes = tuple(
        locale_name.code
        for locale_name in locale_names_map.values()  #
        if not locale_name.installed
    )
    if not_found_codes:
        logging.info('Found locale names which are not installed: %s', not_found_codes)

    for code in tuple(i18next_map.keys()):
        if code not in locale_names_map:
            raise ValueError(f'Installed locale {code!r} has no locale name')

    return i18next_map, tuple(sorted(locale_names_map.values(), key=lambda v: v.code))


@cython.cfunc
def _normalize(code: str) -> str:
    code = code.casefold()  # lowercase
    code = _non_alpha_re.sub('-', code)  # remove non-alpha characters
    code = code.strip('-')  # remove leading and trailing dashes
    return code


_i18next_map, LOCALES_NAMES = _load_locale()
INSTALLED_LOCALES_NAMES = tuple(locale_name for locale_name in LOCALES_NAMES if locale_name.installed)
_installed_locales_codes = frozenset(locale_name.code for locale_name in INSTALLED_LOCALES_NAMES)
_installed_locales_codes_normalized_map = {_normalize(k): k for k in _installed_locales_codes}
logging.info(
    'Loaded %d locales and %d locales names (%d installed)',
    len(_i18next_map),
    len(LOCALES_NAMES),
    len(INSTALLED_LOCALES_NAMES),
)


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
        _i18next_map = _load_locale()[0]

    # i18next supports only primary+fallback locale
    primary_locale = locales[0]
    primary_file = _i18next_map[primary_locale]
    if len(locales) == 1:
        return (primary_file,)
    fallback_locale = locales[-1]
    fallback_file = _i18next_map[fallback_locale]
    return (primary_file, fallback_file)


def is_installed_locale(code: str) -> bool:
    """
    Check if the locale code is installed.

    >>> is_installed_locale('en')
    True
    >>> is_installed_locale('NonExistent')
    False
    """
    return code in _installed_locales_codes


def normalize_locale(code: str) -> str | None:
    """
    Normalize locale code case.

    Returns None if the locale is not installed.

    >>> normalize_locale('EN')
    'en'
    >>> normalize_locale('NonExistent')
    None
    """
    # skip if already normalized
    if code in _installed_locales_codes:
        return code
    return _installed_locales_codes_normalized_map.get(_normalize(code))
