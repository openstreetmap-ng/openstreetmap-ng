import re

import cython

if cython.compiled:
    print(f'{__name__}: 🐇 compiled')

# Safari detection would be nice, but requires more computational resources

_user_agent_re = re.compile(r'(?P<name>Chrome|Firefox)/(?P<major_version>\d{1,4})')


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
    if not match:
        return True

    name = match.group('name')
    major_version: cython.int = int(match.group('major_version'))

    # current target is es2020
    # see: https://www.w3schools.com/Js/js_2020.asp
    if name == 'Chrome':
        return major_version >= 85
    elif name == 'Firefox':
        return major_version >= 79
    else:
        raise NotImplementedError(f'Unsupported browser name {name!r}')
