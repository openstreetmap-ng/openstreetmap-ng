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
    capture_paths: list[re.Pattern[str]] = []
    result: list[str] = []
    for route in app.routes:
        if not isinstance(route, Route):
            continue
        route_path = route.path
        match = path_re.search(route_path)
        if match is None:
            continue
        name = match['display_name']
        if name[0] == '{':
            capture_paths.append(route.path_regex)
            continue
        if any(path_re.match(route_path) for path_re in capture_paths):
            raise AssertionError(
                f'Route {route_path!r} is ordered after matching {capture_paths!r}, this will probably not work'
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
