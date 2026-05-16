import cython
from shapely import Point, get_coordinates

if cython.compiled:
    from cython.cimports.libc.math import atan2, cos, sin, sqrt
else:
    from math import atan2, cos, sin, sqrt


@cython.cfunc
def _radians(degrees: cython.double) -> cython.double:
    return degrees * 0.017453292519943295  # pi / 180


def meters_to_radians(meters: float):
    """Convert a distance in meters to radians."""
    return meters / 6371000  # R


def radians_to_meters(radians: float):
    """Convert a distance in radians to meters."""
    return radians * 6371000  # R


def meters_to_degrees(meters: float):
    """Convert a distance in meters to degrees."""
    return meters / (6371000 / 57.29577951308232)  # R / (180 / pi)


def degrees_to_meters(degrees: float):
    """Convert a distance in degrees to meters."""
    return degrees * (6371000 / 57.29577951308232)  # R / (180 / pi)


def haversine_distance(p1: Point, p2: Point):
    """
    Calculate the distance between two points on the Earth's surface using the Haversine formula.

    Returns the distance in meters.
    """
    coords1 = get_coordinates(p1)[0].tolist()
    lon1: cython.double = coords1[0]
    lat1: cython.double = coords1[1]

    coords2 = get_coordinates(p2)[0].tolist()
    lon2: cython.double = coords2[0]
    lat2: cython.double = coords2[1]

    delta_lon: cython.double = _radians(lon2 - lon1)
    delta_lat: cython.double = _radians(lat2 - lat1)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(_radians(lat1)) * cos(_radians(lat2)) * sin(delta_lon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return c * 6371000  # R
