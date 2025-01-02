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
    last_capture_path: str | None = None
    result: list[str] = []
    for route in app.routes:
        if not isinstance(route, Route):
            continue
        match = path_re.search(route.path)
        if match is None:
            continue
        name = match['display_name']
        if name[0] == '{':
            last_capture_path = route.path
            continue
        if last_capture_path is not None:
            raise AssertionError(
                f'Route {route.path!r} is ordered after capturing {last_capture_path!r}, this will probably not work'
            )
        result.append(_normalize(name))
    _BLACKLIST.update(result)
    logging.info('Blacklisted %d user names from routes: %s', len(result), result)


def is_user_name_blacklisted(display_name: DisplayNameType) -> bool:
    """Check if the given display name is blacklisted."""
    return _normalize(display_name) in _BLACKLIST


@cython.cfunc
def _normalize(s: str) -> str:
    return s.strip().casefold()
