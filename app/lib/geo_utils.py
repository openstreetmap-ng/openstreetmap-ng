import cython
from shapely import MultiPolygon, Point, Polygon, box, get_coordinates

from app.lib.exceptions_context import raise_for
from app.validators.geometry import validate_geometry

if cython.compiled:
    from cython.cimports.libc.math import atan2, cos, sin, sqrt
else:
    from math import atan2, cos, sin, sqrt


@cython.cfunc
def radians(x: cython.double) -> cython.double:
    return x * 0.017453292519943295  # pi / 180


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
    coords1 = get_coordinates(p1)[0]
    lon1: cython.double = coords1[0]
    lat1: cython.double = coords1[1]

    coords2 = get_coordinates(p2)[0]
    lon2: cython.double = coords2[0]
    lat2: cython.double = coords2[1]

    delta_lon: cython.double = radians(lon2 - lon1)
    delta_lat: cython.double = radians(lat2 - lat1)

    a = sin(delta_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return c * 6371000  # R


def parse_bbox(s: str) -> Polygon | MultiPolygon:
    """
    Parse a bbox string or bounds.

    Returns a Polygon or MultiPolygon (if crossing the antimeridian).

    Raises exception if the string is not in a valid format.

    >>> parse_bbox('1,2,3,4')
    POLYGON ((1 2, 1 4, 3 4, 3 2, 1 2))
    """
    try:
        parts = s.strip().split(',', maxsplit=3)
        minx: cython.double = float(parts[0])
        miny: cython.double = float(parts[1])
        maxx: cython.double = float(parts[2])
        maxy: cython.double = float(parts[3])
    except Exception:
        raise_for().bad_bbox(s)
    if minx > maxx:
        raise_for().bad_bbox(s, 'min longitude > max longitude')
    if miny > maxy:
        raise_for().bad_bbox(s, 'min latitude > max latitude')

    # normalize latitude
    if miny < -90:
        miny = -90
    if maxy > 90:
        maxy = 90

    # special case, bbox wraps around the whole world
    if maxx - minx >= 360:
        return validate_geometry(box(-180, miny, 180, maxy))

    # normalize minx to [-180, 180), maxx to [minx, minx + 360)
    if minx < -180 or maxx > 180:
        offset: cython.double = ((minx + 180) % 360 - 180) - minx
        minx += offset
        maxx += offset

    # simple geometry, no meridian crossing
    if maxx <= 180:
        return validate_geometry(box(minx, miny, maxx, maxy))

    # meridian crossing
    return validate_geometry(
        MultiPolygon(
            (
                box(minx, miny, 180, maxy),
                box(-180, miny, maxx - 360, maxy),
            )
        )
    )
