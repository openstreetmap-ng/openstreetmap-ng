import logging
import pathlib

from config import DEFAULT_LANGUAGE

_locales: set[str] = set()

for p in pathlib.Path('config/locale').iterdir():
    if not p.is_dir():
        continue

    _locales.add(p.name)

_locales = frozenset(_locales)
_locales_lower_map = {k.lower(): k for k in _locales}

logging.info('Loaded %d locales', len(_locales))

if DEFAULT_LANGUAGE not in _locales:
    raise RuntimeError(f'{DEFAULT_LANGUAGE=!r} not found in locales')


def resolve_locale_case(code: str) -> str | None:
    if code in _locales:
        return code

    return _locales_lower_map.get(code.lower(), None)
