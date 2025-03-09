import logging
import re
from itertools import chain
from pathlib import Path
from typing import NamedTuple

import cython
import orjson

from app.config import FORCE_RELOAD_LOCALE_FILES
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

_NON_ALPHA_RE = re.compile(r'[^a-z]+')


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

    not_found = [
        locale_name.code
        for locale_name in locale_names_map.values()  #
        if not locale_name.installed
    ]
    if not_found:
        logging.info('Found locale names which are not installed: %s', not_found)

    for code in i18next_map:
        if code not in locale_names_map:
            raise ValueError(f'Installed locale {code!r} has no locale name')

    return i18next_map, locale_names_map


@cython.cfunc
def _normalize(code: LocaleCode):
    # lowercase -> remove non-alpha characters -> remove leading and trailing dashes
    return LocaleCode(_NON_ALPHA_RE.sub('-', code.casefold()).strip('-'))


_I18NEXT_MAP, LOCALES_NAMES_MAP = _load_locale()
INSTALLED_LOCALES_NAMES_MAP = {
    code: locale_name
    for code, locale_name in LOCALES_NAMES_MAP.items()  #
    if locale_name.installed
}
_INSTALLED_LOCALES_CODES_NORMALIZED_MAP = {_normalize(k): k for k in INSTALLED_LOCALES_NAMES_MAP}
logging.info(
    'Loaded %d locales and %d locales names (%d installed)',
    len(_I18NEXT_MAP),
    len(LOCALES_NAMES_MAP),
    len(INSTALLED_LOCALES_NAMES_MAP),
)


def map_i18next_files(locales: tuple[LocaleCode, ...]) -> list[str]:
    """
    Map the locales to i18next files.
    Returns at most two files: primary and fallback locale.
    >>> map_i18next_files([LocaleCode('pl'), LocaleCode('en'), LocaleCode('de')])
    ('pl-e4c39a792074d67c.js', 'en-c39c7633ceb0ce46.js')
    """
    result = [_I18NEXT_MAP[locales[0]]]
    if len(locales) > 1:
        result.append(_I18NEXT_MAP[locales[-1]])
    return result


# optionally wrap map_i18next_files to always regenerate _i18next_map
if FORCE_RELOAD_LOCALE_FILES:
    _map_i18next_files_inner = map_i18next_files

    def map_i18next_files(locales: tuple[LocaleCode, ...]) -> list[str]:
        global _I18NEXT_MAP
        _I18NEXT_MAP = _load_locale()[0]  # pyright: ignore [reportConstantRedefinition]
        return _map_i18next_files_inner(locales)


def is_installed_locale(code: LocaleCode) -> bool:
    """
    Check if the locale code is installed.

    >>> is_installed_locale(LocaleCode('en'))
    True
    >>> is_installed_locale(LocaleCode('NonExistent'))
    False
    """
    return code in INSTALLED_LOCALES_NAMES_MAP


def normalize_locale(code: LocaleCode) -> LocaleCode | None:
    """
    Normalize locale code case.
    Returns None if the locale is not installed.

    >>> normalize_locale(LocaleCode('EN'))
    'en'
    >>> normalize_locale(LocaleCode('NonExistent'))
    None
    """
    return (
        code
        if code in INSTALLED_LOCALES_NAMES_MAP  #
        else _INSTALLED_LOCALES_CODES_NORMALIZED_MAP.get(_normalize(code))
    )
