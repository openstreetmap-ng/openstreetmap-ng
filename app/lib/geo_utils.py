from collections.abc import Generator

import cython
from shapely.geometry import Point, Polygon, shape
from shapely.ops import BaseGeometry

from app.lib.exceptions_context import raise_for

if cython.compiled:
    from cython.cimports.libc.math import atan2, cos, pi, sin, sqrt
else:
    from math import atan2, cos, pi, sin, sqrt


# @cython.cfunc
#
# def degrees(x: cython.double) -> cython.double:
#     return x * (180 / pi)


@cython.cfunc
def radians(x: cython.double) -> cython.double:
    return x * (pi / 180)


def meters_to_radians(meters: float) -> float:
    """
    Convert a distance in meters to radians.

    >>> meters_to_radians(1000)
    0.008993216059693147
    """

    return meters / 6371000  # R


def radians_to_meters(radians: float) -> float:
    """
    Convert a distance in radians to meters.

    >>> radians_to_meters(0.008993216059693147)
    1000.0
    """

    return radians * 6371000  # R


def haversine_distance(p1: Point, p2: Point) -> float:
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


def validate_geometry(value: dict | BaseGeometry) -> BaseGeometry:
    """
    Validate a geometry.
    """

    if isinstance(value, dict):
        value = shape(value)

    if not value.is_valid:
        raise_for().bad_geometry()

    lon: cython.double
    lat: cython.double

    for lon, lat in _geom_points(value):
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise_for().bad_geometry_coordinates(lon, lat)
            # TODO: 0.7:
            # raise ValueError(f'Invalid coordinates {lon=!r} {lat=!r}. '
            #                  f'Please ensure longitude and latitude are in the EPSG:4326/WGS84 format.')

    return value


@cython.cfunc
def _geom_points(geom: BaseGeometry) -> tuple[tuple[float, float], ...]:
    """
    Get all points from a geometry.

    Returns a sequence of (lon, lat) tuples.

    >>> _geom_points(Polygon([(1, 2), (3, 4), (5, 6)]))
    [(1, 2), (3, 4), (5, 6)]
    """

    # read property once for performance
    geom_type: str = geom.type

    if geom_type == 'Point':
        return ((geom.x, geom.y),)
    elif geom_type == 'MultiPoint':
        return tuple((point.x, point.y) for point in geom.geoms)
    elif geom_type == 'LineString':
        return tuple(geom.coords)
    elif geom_type == 'MultiLineString':
        return tuple(point for line in geom.geoms for point in line.coords)
    elif geom_type == 'Polygon':
        return tuple(geom.exterior.coords) + tuple(point for interior in geom.interiors for point in interior.coords)
    elif geom_type == 'MultiPolygon':
        result = []
        for polygon in geom.geoms:
            result.extend(polygon.exterior.coords)
            result.extend(point for interior in polygon.interiors for point in interior.coords)
        return tuple(result)
    else:
        raise_for().bad_geometry()
