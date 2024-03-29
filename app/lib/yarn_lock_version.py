import logging
import pathlib
import re

import cython


@cython.cfunc
def _get_yarn_lock_versions() -> dict[str, str]:
    lock = pathlib.Path('yarn.lock').read_text()
    result = {}

    for match in re.finditer(r'^"?(\S+?)@.*?version "(\S+?)"', lock, re.MULTILINE | re.DOTALL):
        name = match[1]
        version = match[2]
        version = version.rpartition('#')[2]  # use hash if available
        result[name] = version

    return result


_yarn_lock_versions = _get_yarn_lock_versions()


def yarn_lock_version(name: str) -> str:
    """
    Get the version of a package from yarn.lock.

    >>> yarn_lock_version('i18next-http-backend')
    '2.4.2'
    >>> yarn_lock_version('iD')
    '60eb7d7'
    """
    result = _yarn_lock_versions[name]
    logging.info('Yarn lock for %s is %s', name, result)
    return result
