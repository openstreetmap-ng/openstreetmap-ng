import logging
import os
from collections import UserDict
from collections.abc import Mapping
from typing import override

import cython

from app.config import TEST_ENV


@cython.cfunc
def _get_mapping() -> dict[str, str]:
    result: dict[str, str] = {}
    path_mtime: dict[str, float] = {}

    for dir in ('app/static/js', 'app/static/css'):
        with os.scandir(dir) as it:
            for entry in it:
                if not entry.is_file():
                    continue

                path: str = entry.path
                parts: list[str] = entry.name.split('.', 2)
                if len(parts) == 3 and 6 <= len(parts[1]) <= 12:
                    path = f'{dir}/{parts[0]}.{parts[2]}'

                mtime = entry.stat().st_mtime
                if path_mtime.get(path, 0) > mtime:
                    continue

                result[path[3:]] = entry.path[3:]  # strip 'app' prefix
                path_mtime[path] = mtime

    return result


HASH_AWARE_PATHS: Mapping[str, str]
"""
Mapping to hash-aware paths.

>>> HASH_AWARE_PATHS['/static/js/main.js']
'/static/js/main.wcb165d8.js'
"""

if TEST_ENV:
    # In test environment, update the mapping on each access

    class _UpdatingHashAwarePaths(UserDict):
        @override
        def __getitem__(self, key):
            self.data = data = _get_mapping()
            return data[key]

    HASH_AWARE_PATHS = _UpdatingHashAwarePaths()  # pyright: ignore [reportConstantRedefinition]

else:
    HASH_AWARE_PATHS = _get_mapping()  # pyright: ignore [reportConstantRedefinition]

logging.debug('Static asset hash mapping has %d entries', len(HASH_AWARE_PATHS))
