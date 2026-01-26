import logging

import cython
import re2
from starlette.applications import Starlette
from starlette.routing import Route

from app.models.types import DisplayName

_BLACKLIST = set[str]()
_USER_PATH_RE = re2.compile(r'^/user/([^/{][^/]*)')


def user_name_blacklist_routes(app: Starlette):
    """Blacklist usernames that could conflict with application routes."""
    result: list[str] = []

    for route in app.routes:
        if not isinstance(route, Route):
            continue

        match = _USER_PATH_RE.match(route.path)
        if match is not None:
            result.append(_normalize(match[1]))

    _BLACKLIST.update(result)
    logging.info('Blacklisted %d user names from routes: %s', len(result), result)


def is_user_name_blacklisted(display_name: DisplayName):
    """Check if the given display name is blacklisted."""
    return _normalize(display_name) in _BLACKLIST


@cython.cfunc
def _normalize(s: str):
    return s.strip().casefold()
