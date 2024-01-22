import logging
import pathlib
from collections.abc import Sequence

import orjson

from app.config import CONFIG_DIR, DEFAULT_LANGUAGE, LOCALE_DIR
from app.limits import LANGUAGE_CODE_MAX_LENGTH
from app.models.locale_name import LocaleName


def _get_locales():
    return frozenset(p.stem for p in pathlib.Path(LOCALE_DIR).iterdir() if p.is_file() and p.suffix == '.yml')


def _get_locales_names():
    data = orjson.loads(pathlib.Path(CONFIG_DIR / 'locales_names.json').read_bytes())
    return tuple(sorted((LocaleName(**d) for d in data), key=lambda v: v.code))


_locales = _get_locales()
_locales_lower_map = {k.casefold(): k for k in _locales}
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


def normalize_locale_case(code: str, *, raise_on_not_found: bool = False) -> str:
    """
    Normalize locale code case.

    >>> normalize_locale_case('EN')
    'en'
    >>> normalize_locale_case('NonExistent', raise_on_not_found=True)
    KeyError: 'NonExistent'
    """

    if code in _locales:
        return code

    if raise_on_not_found:
        return _locales_lower_map[code.casefold()]
    else:
        return _locales_lower_map.get(code.casefold(), code)


def get_all_locales_names() -> Sequence[LocaleName]:
    """
    Get all locales names sorted by code.

    >>> get_all_locales_names()
    [LocaleName(code='pl', english='Polish', native='Polski'), ...]
    """

    return _locales_names
