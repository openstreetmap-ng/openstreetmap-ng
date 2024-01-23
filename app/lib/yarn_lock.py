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


def get_yarn_lock_version(name: str) -> str:
    """
    Get the version of a package from yarn.lock.

    >>> get_yarn_lock_version('i18next-http-backend')
    '2.4.2'
    >>> get_yarn_lock_version('iD')
    '60eb7d7'
    """

    return _yarn_lock_versions[name]
