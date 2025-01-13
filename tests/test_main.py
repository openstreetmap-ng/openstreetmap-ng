import re
from collections import defaultdict

from starlette.routing import Route

from app.main import main


def test_route_conflicts():
    capture_paths: defaultdict[str, list[re.Pattern[str]]] = defaultdict(list)
    for route in main.routes:
        if not isinstance(route, Route):
            continue
        route_methods = route.methods or ()
        for p in (p for method in route_methods for p in capture_paths[method]):
            if p.match(route.path):
                raise AssertionError(
                    f'Route {route.path!r} is ordered after matching {p.pattern!r}, this will probably not work'
                )
        for method in route_methods:
            capture_paths[method].append(route.path_regex)
