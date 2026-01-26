import logging
from functools import lru_cache

import orjson
import re2

from app.config import FILE_CACHE_DIR

# Safari detection would be nice, but requires more complex checks
_USER_AGENT_RE = re2.compile(r'(Chrome|Firefox)/(\d{1,4})')


@lru_cache(maxsize=512)
def is_browser_supported(user_agent: str):
    """
    Check if the given user agent supports the targeted web standards.

    >>> is_browser_supported('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.104 Safari/537.36')
    False
    """
    # support empty user agents
    if not user_agent:
        return True

    match = _USER_AGENT_RE.search(user_agent)

    # support unknown user agents
    if match is None:
        return True

    name, major_version = match[1], int(match[2])

    if name == 'Chrome':
        return major_version >= _CHROME_MAJOR_VERSION
    elif name == 'Firefox':
        return major_version >= _FIREFOX_MAJOR_VERSION

    raise NotImplementedError(f'Unsupported browser name {name!r}')


_data = orjson.loads(FILE_CACHE_DIR.joinpath('browserslist_versions.json').read_bytes())
_CHROME_MAJOR_VERSION = int(_data['chrome'])
_FIREFOX_MAJOR_VERSION = int(_data['firefox'])
logging.info(
    'Supported browsers: Chrome=%d, Firefox=%d',
    _CHROME_MAJOR_VERSION,
    _FIREFOX_MAJOR_VERSION,
)
del _data
