import logging
import re
from pathlib import Path

import cython


@cython.cfunc
def _parse_yarn_lock() -> dict[str, str]:
    lock = Path('yarn.lock').read_text()
    result = {}
    for match in re.finditer(r'^"?(\S+?)@.*?version "(\S+?)"', lock, re.MULTILINE | re.DOTALL):
        name = match[1]
        version = match[2]
        version = version.rpartition('#')[2]  # use hash if available
        result[name] = version
    return result


_package_versions = _parse_yarn_lock()


@cython.cfunc
def _package_version(name: str) -> str:
    """
    Get the version of a package from yarn.lock.

    >>> _package_version('i18next-http-backend')
    '2.4.2'
    >>> _package_version('iD')
    '60eb7d7'
    """
    result = _package_versions[name]
    logging.info('Yarn lock for %s is %s', name, result)
    return result


ID_VERSION = _package_version('iD')
RAPID_VERSION = _package_version('@rapideditor/rapid')
