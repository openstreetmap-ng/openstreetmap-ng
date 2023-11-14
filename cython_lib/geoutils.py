import cython
from cython.cimports.libc.math import atan2, cos, pi, sin, sqrt
from shapely.geometry import Point


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
