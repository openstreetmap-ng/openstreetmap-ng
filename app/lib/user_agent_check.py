import json
import logging
import os
import re
import subprocess
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import cython

from app.config import FILE_CACHE_DIR

# Safari detection would be nice, but requires more complex checks
_user_agent_re = re.compile(r'(?P<name>Chrome|Firefox)/(?P<major_version>\d{1,4})')


@lru_cache(maxsize=512)
def is_browser_supported(user_agent: str) -> bool:
    """
    Check if the given user agent supports the targeted web standards.

    >>> is_browser_supported('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.104 Safari/537.36')
    False
    """
    # support empty user agents
    if not user_agent:
        return True

    match = _user_agent_re.search(user_agent)

    # support unknown user agents
    if match is None:
        return True

    name: str = match['name']
    major_version = int(match['major_version'])

    if name == 'Chrome':
        return major_version >= _CHROME_MAJOR_VERSION
    elif name == 'Firefox':
        return major_version >= _FIREFOX_MAJOR_VERSION
    else:
        raise NotImplementedError(f'Unsupported browser name {name!r}')


@cython.cfunc
def _browserslist_versions() -> dict[str, float]:
    """
    Get the mapping of supported browsers to their minimum versions.
    """
    lock_path = Path('package.json')
    lock_mtime = lock_path.stat().st_mtime
    cache_path = FILE_CACHE_DIR / 'browserslist_versions.json'
    if not cache_path.is_file() or lock_mtime > cache_path.stat().st_mtime:
        stdout = subprocess.check_output(('bunx', 'browserslist'), env={**os.environ, 'NO_COLOR': '1'}).decode()  # noqa: S603
        result: dict[str, float] = defaultdict(lambda: float('inf'))
        for line in stdout.splitlines():
            browser, _, version = line.partition(' ')
            version = min(float(v) for v in version.split('-'))
            result[browser] = min(result[browser], version)
        cache_path.write_text(json.dumps(result))
        os.utime(cache_path, (lock_mtime, lock_mtime))
    return json.loads(cache_path.read_bytes())


_data = _browserslist_versions()
_CHROME_MAJOR_VERSION = int(_data['chrome'])
_FIREFOX_MAJOR_VERSION = int(_data['firefox'])
logging.info('Supported browsers: Chrome=%d, Firefox=%d', _CHROME_MAJOR_VERSION, _FIREFOX_MAJOR_VERSION)
del _data
