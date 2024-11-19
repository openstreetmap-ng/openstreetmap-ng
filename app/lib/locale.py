import logging
import re
from collections.abc import Sequence
from itertools import chain
from pathlib import Path
from typing import NamedTuple

import cython
import orjson

from app.config import TEST_ENV
from app.limits import LOCALE_CODE_MAX_LENGTH
from app.models.types import LocaleCode


class LocaleName(NamedTuple):
    code: LocaleCode
    english: str
    native: str
    installed: bool

    @property
    def display_name(self) -> str:
        return self.english if (self.english == self.native) else f'{self.english} ({self.native})'


DEFAULT_LOCALE = LocaleCode('en')

_non_alpha_re = re.compile(r'[^a-z]+')


@cython.cfunc
def _load_locale() -> tuple[dict[LocaleCode, str], dict[LocaleCode, LocaleName]]:
    i18next_map: dict[LocaleCode, str] = orjson.loads(Path('config/locale/i18next/map.json').read_bytes())
    locales_codes_normalized_map = {_normalize(k): k for k in i18next_map}
    # TODO: use osm language data
    raw_names: list[dict[str, str]] = orjson.loads(Path('config/locale/names.json').read_bytes())
    locale_names_map: dict[LocaleCode, LocaleName] = {}

    for raw_name in sorted(raw_names, key=lambda v: v['english'].casefold()):
        code = LocaleCode(raw_name.pop('code'))
        installed = code in i18next_map
        locale_name = LocaleName(**raw_name, code=code, installed=installed)
        if not locale_name.installed:
            new_code = locales_codes_normalized_map.get(_normalize(locale_name.code))
            if new_code is not None:
                raise ValueError(f'Locale code {locale_name.code!r} is mistyped, expected {new_code!r}')
        locale_names_map[locale_name.code] = locale_name

    # check that default locale exists
    if DEFAULT_LOCALE not in i18next_map:
        raise ValueError(f'Default locale {DEFAULT_LOCALE!r} was not found in installed locales')
    # check that all language codes are short enough
    for code in chain(i18next_map, locale_names_map):
        if len(code) > LOCALE_CODE_MAX_LENGTH:
            raise ValueError(f'Locale code {code!r} is too long ({len(code)} > {LOCALE_CODE_MAX_LENGTH})')

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

    return i18next_map, locale_names_map


@cython.cfunc
def _normalize(code: LocaleCode):
    # lowercase -> remove non-alpha characters -> remove leading and trailing dashes
    return LocaleCode(_non_alpha_re.sub('-', code.casefold()).strip('-'))


_i18next_map, LOCALES_NAMES_MAP = _load_locale()
INSTALLED_LOCALES_NAMES_MAP = {
    code: locale_name
    for code, locale_name in LOCALES_NAMES_MAP.items()  #
    if locale_name.installed
}
_installed_locales_codes_normalized_map = {_normalize(k): k for k in INSTALLED_LOCALES_NAMES_MAP}
logging.info(
    'Loaded %d locales and %d locales names (%d installed)',
    len(_i18next_map),
    len(LOCALES_NAMES_MAP),
    len(INSTALLED_LOCALES_NAMES_MAP),
)


def map_i18next_files(locales: Sequence[LocaleCode]) -> tuple[str, ...]:
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


def is_installed_locale(code: LocaleCode) -> bool:
    """
    Check if the locale code is installed.

    >>> is_installed_locale('en')
    True
    >>> is_installed_locale('NonExistent')
    False
    """
    return code in INSTALLED_LOCALES_NAMES_MAP


def normalize_locale(code: LocaleCode) -> LocaleCode | None:
    """
    Normalize locale code case.

    Returns None if the locale is not installed.

    >>> normalize_locale('EN')
    'en'
    >>> normalize_locale('NonExistent')
    None
    """
    # skip if already normalized
    if code in INSTALLED_LOCALES_NAMES_MAP:
        return code
    return _installed_locales_codes_normalized_map.get(_normalize(code))
