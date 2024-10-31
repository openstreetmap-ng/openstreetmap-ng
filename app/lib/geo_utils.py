import cython
from shapely import MultiPolygon, Point, Polygon, box, get_coordinates

from app.lib.exceptions_context import raise_for
from app.limits import GEO_COORDINATE_PRECISION
from app.validators.geometry import validate_geometry

if cython.compiled:
    from cython.cimports.libc.math import atan2, cos, sin, sqrt
else:
    from math import atan2, cos, sin, sqrt


@cython.cfunc
def radians(degrees: cython.double) -> cython.double:
    return degrees * 0.017453292519943295  # pi / 180


def meters_to_radians(meters: float) -> float:
    """
    Convert a distance in meters to radians.

    >>> meters_to_radians(1000)
    0.000156...
    """
    return meters / 6371000  # R


def radians_to_meters(radians: float) -> float:
    """
    Convert a distance in radians to meters.

    >>> radians_to_meters(0.000156...)
    1000.0
    """
    return radians * 6371000  # R


def meters_to_degrees(meters: float) -> float:
    """
    Convert a distance in meters to degrees.

    >>> meters_to_degrees(1000)
    0.00899...
    """
    return meters / (6371000 / 57.29577951308232)  # R / (180 / pi)


def degrees_to_meters(degrees: float) -> float:
    """
    Convert a distance in degrees to meters.

    >>> degrees_to_meters(0.00899...)
    1000.0
    """
    return degrees * (6371000 / 57.29577951308232)  # R / (180 / pi)


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
    parts = s.strip().split(',', maxsplit=3)
    try:
        precision = GEO_COORDINATE_PRECISION
        minx: cython.double = round(float(parts[0].strip()), precision)
        miny: cython.double = round(float(parts[1].strip()), precision)
        maxx: cython.double = round(float(parts[2].strip()), precision)
        maxy: cython.double = round(float(parts[3].strip()), precision)
    except Exception:
        raise_for().bad_bbox(s)
    if minx > maxx:
        raise_for().bad_bbox(s, 'min longitude > max longitude')
    if miny > maxy:
        raise_for().bad_bbox(s, 'min latitude > max latitude')

    # normalize latitude
    miny = max(miny, -90)
    maxy = min(maxy, 90)

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


def try_parse_point(lat_lon: str) -> Point | None:
    """
    Try to parse a point string.

    Returns None if the string is not in a valid format.

    >>> try_parse_point('1,2')
    POINT (2 1)
    """
    lat_str, _, lon_str = lat_lon.partition(',')
    if not lon_str:
        lat_str, _, lon_str = lat_lon.partition(' ')
    if not lon_str:
        return None
    try:
        precision = GEO_COORDINATE_PRECISION
        lon = round(float(lon_str.strip()), precision)
        lat = round(float(lat_str.strip()), precision)
    except ValueError:
        return None
    try:
        return validate_geometry(Point(lon, lat))
    except Exception:
        return None
