import logging
import re
import tomllib
import unicodedata
from pathlib import Path
from typing import NamedTuple, overload

import cython
import orjson

from app.config import ENV, LOCALE_CODE_MAX_LENGTH
from app.models.types import LocaleCode


class LocaleName(NamedTuple):
    code: LocaleCode
    english: str
    native: str
    installed: bool
    flag: str | None

    @property
    def display_name(self) -> str:
        return (
            self.native
            if self.english == self.native
            else f'{self.native} ({self.english})'
        )


DEFAULT_LOCALE = LocaleCode('en')

_NON_ALPHA_RE = re.compile(r'[^a-z]+')


@cython.cfunc
def _get_flag(
    code: str, flags: dict[str, str], flags_passthrough: set[str]
) -> str | None:
    parts = code.upper().split('-')

    for i in range(len(parts), 0, -1):
        code = '-'.join(parts[:i])

        flag_code = code if code in flags_passthrough else flags.get(code)
        if flag_code is None:
            continue

        # Handle subdivision flags (format: CC-SUB, e.g., GB-WLS)
        code_parts = flag_code.split('-')
        if len(code_parts) == 2:
            # Build Unicode subdivision flag:
            # black flag + country tags + subdivision tags + cancel tag
            return ''.join((
                '🏴',
                *(chr(0xE0000 + ord(c)) for cp in code_parts for c in cp.lower()),
                '\U000e007f',
            ))

        try:
            emoji = ''.join(chr(0x1F1A5 + ord(c)) for c in flag_code)
            if all(
                unicodedata.name(c, '').startswith('REGIONAL INDICATOR SYMBOL')
                for c in emoji
            ):
                return emoji
        except (ValueError, OverflowError):
            continue

    return None


@cython.cfunc
def _load_locale() -> tuple[dict[LocaleCode, str], dict[LocaleCode, LocaleName]]:
    i18next_map: dict[LocaleCode, str]
    i18next_map = orjson.loads(Path('config/locale/i18next/map.json').read_bytes())
    locales_codes_normalized_map = {_normalize(k): k for k in i18next_map}

    # TODO: use osm language data

    raw_names: list[dict[str, str]]
    raw_names = orjson.loads(Path('config/locale/names.json').read_bytes())
    raw_names.sort(key=lambda v: (v['native'] or v['english']).casefold())
    locale_names_map: dict[LocaleCode, LocaleName] = {}

    flags = tomllib.loads(Path('config/locale/flags.toml').read_text())
    flags_passthrough = set(flags.pop('passthrough'))

    for raw_name in raw_names:
        code = LocaleCode(raw_name.pop('code'))
        locale_name = LocaleName(
            **raw_name,
            code=code,
            installed=code in i18next_map,
            flag=_get_flag(code, flags, flags_passthrough),
        )

        if not locale_name.installed:
            new_code = locales_codes_normalized_map.get(_normalize(locale_name.code))
            if new_code is not None:
                raise ValueError(
                    f'Locale code {locale_name.code!r} is mistyped, expected {new_code!r}'
                )

        locale_names_map[locale_name.code] = locale_name

    # Check that the default locale is installed
    if DEFAULT_LOCALE not in i18next_map:
        raise ValueError(
            f'Default locale {DEFAULT_LOCALE!r} was not found in installed locales'
        )

    # Check that all i18next locales have a name
    for code in i18next_map:
        if code not in locale_names_map:
            raise ValueError(f'Installed locale {code!r} has no locale name')

    # Check lengths of all locale codes
    for code in (*i18next_map, *locale_names_map):
        if len(code) > LOCALE_CODE_MAX_LENGTH:
            raise ValueError(
                f'Locale code {code!r} is too long ({len(code)} > {LOCALE_CODE_MAX_LENGTH})'
            )

    return i18next_map, locale_names_map


@cython.cfunc
def _normalize(code: LocaleCode):
    # lowercase -> remove non-alpha characters -> remove leading and trailing dashes
    return LocaleCode(_NON_ALPHA_RE.sub('-', code.casefold()).strip('-'))


_I18NEXT_MAP, LOCALES_NAMES_MAP = _load_locale()
INSTALLED_LOCALES_NAMES_MAP = {
    code: locale_name
    for code, locale_name in LOCALES_NAMES_MAP.items()
    if locale_name.installed
}
_INSTALLED_LOCALES_CODES_NORMALIZED_MAP = {
    _normalize(code): code for code in INSTALLED_LOCALES_NAMES_MAP
}
logging.info(
    'Loaded %d locales and %d locales names (%d installed + %d not installed)',
    len(_I18NEXT_MAP),
    len(LOCALES_NAMES_MAP),
    len(INSTALLED_LOCALES_NAMES_MAP),
    len([ln.code for ln in LOCALES_NAMES_MAP.values() if not ln.installed]),
)


def map_i18next_files(locales: tuple[LocaleCode, ...]) -> tuple[str] | tuple[str, str]:
    """
    Map the locales to i18next files.
    Returns at most two files: primary and fallback locale.

    >>> map_i18next_files((LocaleCode('pl'), LocaleCode('en'), LocaleCode('de')))
    ('pl-e4c39a792074d67c.js', 'en-c39c7633ceb0ce46.js')
    """
    return (
        (_I18NEXT_MAP[locales[0]],)
        if len(locales) == 1
        else (_I18NEXT_MAP[locales[0]], _I18NEXT_MAP[locales[-1]])
    )


# Live reloading of translations in dev environment
if ENV == 'dev':
    _map_i18next_files_inner = map_i18next_files

    def map_i18next_files(
        locales: tuple[LocaleCode, ...],
    ) -> tuple[str] | tuple[str, str]:
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


@overload
def normalize_locale(code: None) -> None: ...
@overload
def normalize_locale(code: LocaleCode) -> LocaleCode | None: ...
def normalize_locale(code: LocaleCode | None) -> LocaleCode | None:
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
        if code is None or code in INSTALLED_LOCALES_NAMES_MAP
        else _INSTALLED_LOCALES_CODES_NORMALIZED_MAP.get(_normalize(code))
    )
