import logging
import pathlib

import cython

from src.config import DEFAULT_LANGUAGE, LOCALE_DIR

if cython.compiled:
    print(f'{__name__}: 🐇 compiled')

_locales: frozenset[str] = frozenset(p.name for p in pathlib.Path(LOCALE_DIR).iterdir() if p.is_dir())
_locales_lower_map = {k.casefold(): k for k in _locales}

logging.info('Loaded %d locales', len(_locales))

# check that default locale exists
if DEFAULT_LANGUAGE not in _locales:
    raise RuntimeError(f'{DEFAULT_LANGUAGE=!r} not found in locales')


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
