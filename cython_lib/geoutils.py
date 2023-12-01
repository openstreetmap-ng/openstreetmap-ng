import cython
from shapely.geometry import Point, Polygon

from lib.exceptions import raise_for
from validators.geometry import validate_geometry

if cython.compiled:
    from cython.cimports.libc.math import atan2, cos, pi, sin, sqrt

    print(f'{__name__}: 🐇 compiled')
else:
    from math import atan2, cos, pi, sin, sqrt

    print(f'{__name__}: 🐌 not compiled')


@cython.cfunc
def degrees(x: cython.double) -> cython.double:
    return x * (180 / pi)


@cython.cfunc
def radians(x: cython.double) -> cython.double:
    return x * (pi / 180)


def meters_to_radians(meters: cython.double) -> cython.double:
    """
    Convert a distance in meters to radians.

    >>> meters_to_radians(1000)
    0.008993216059693147
    """

    return meters / 6371000  # R


def radians_to_meters(radians: cython.double) -> cython.double:
    """
    Convert a distance in radians to meters.

    >>> radians_to_meters(0.008993216059693147)
    1000.0
    """

    return radians * 6371000  # R


def haversine_distance(p1: Point, p2: Point) -> cython.double:
    """
    Calculate the distance between two points on the Earth's surface using the Haversine formula.

    Returns the distance in meters.
    """

    lon1: cython.double = p1.x
    lat1: cython.double = p1.y
    lon2: cython.double = p2.x
    lat2: cython.double = p2.y

    dlon = radians(lon2 - lon1)
    dlat = radians(lat2 - lat1)

    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return c * 6371000  # R


def parse_bbox(s: str) -> Polygon:
    """
    Parse a bbox string.

    Raises exception if the string is not a valid bbox format.

    >>> parse_bbox('1,2,3,4')
    POLYGON ((1 2, 1 4, 3 4, 3 2, 1 2))
    """

    try:
        parts = s.strip().split(',', maxsplit=3)
        minx, miny, maxx, maxy = map(float, parts)
    except Exception:
        raise_for().bad_bbox(s)
    if minx > maxx:
        raise_for().bad_bbox(s, 'min longitude > max longitude')
    if miny > maxy:
        raise_for().bad_bbox(s, 'min latitude > max latitude')

    # skip box() call for some extra performance
    coords = (
        (maxx, miny),
        (maxx, maxy),
        (minx, maxy),
        (minx, miny),
    )

    return validate_geometry(Polygon(coords))
