import logging
import re

import cython
from starlette.applications import Starlette
from starlette.routing import Route

from app.models.types import DisplayNameType

_BLACKLIST: set[str] = set()


def user_name_blacklist_routes(app: Starlette) -> None:
    """Blacklist usernames that could conflict with application routes."""
    path_re = re.compile(r'^/user/(?P<display_name>[^/]+)')
    result: list[str] = []
    for route in app.routes:
        if not isinstance(route, Route):
            continue
        match = path_re.search(route.path)
        if match is None:
            continue
        name = match['display_name']
        if name[0] == '{':
            continue
        result.append(_normalize(name))
    _BLACKLIST.update(result)
    logging.info('Blacklisted %d user names from routes: %s', len(result), result)


def is_user_name_blacklisted(display_name: DisplayNameType) -> bool:
    """Check if the given display name is blacklisted."""
    return _normalize(display_name) in _BLACKLIST


@cython.cfunc
def _normalize(s: str) -> str:
    return s.strip().casefold()
