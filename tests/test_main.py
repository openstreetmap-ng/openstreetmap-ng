from collections import defaultdict

from starlette.routing import Route

from app.main import main


def test_route_conflicts():
    capture_paths = defaultdict(list)

    for route in main.routes:
        if not isinstance(route, Route) or not (route_methods := route.methods):
            continue

        for p in (p for method in route_methods for p in capture_paths[method]):
            assert not p.match(route.path), (
                f'Route {route.path!r} is ordered after matching {p.pattern!r}'
            )

        for method in route_methods:
            capture_paths[method].append(route.path_regex)
