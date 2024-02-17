import re
from functools import lru_cache

import cython

# Safari detection would be nice, but requires more computational resources

_user_agent_re = re.compile(r'(?P<name>Chrome|Firefox)/(?P<major_version>\d{1,4})')


@lru_cache(maxsize=256)
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

    name = match['name']
    major_version: cython.int = int(match['major_version'])

    # run `bunx browserslist` to see which versions are supported
    if name == 'Chrome':
        return major_version >= 72
    elif name == 'Firefox':
        return major_version >= 68
    else:
        raise NotImplementedError(f'Unsupported browser name {name!r}')
