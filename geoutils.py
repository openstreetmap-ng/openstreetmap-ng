from shapely.geometry import Polygon, box

from lib.exceptions import raise_for
from validators.geometry import validate_geometry


def parse_bbox(s: str) -> Polygon:
    """
    Parse a bbox string.

    Raises exception if the string is not a valid bbox format.

    >>> parse_bbox('1,2,3,4')
    POLYGON ((1 2, 1 4, 3 4, 3 2, 1 2))
    """

    try:
        parts = s.split(',', maxsplit=3)
        minx, miny, maxx, maxy = map(float, (s.strip() for s in parts))
    except Exception:
        raise_for().bad_bbox(s)
    if minx > maxx:
        raise_for().bad_bbox(s, 'min longitude > max longitude')
    if miny > maxy:
        raise_for().bad_bbox(s, 'min latitude > max latitude')
    return validate_geometry(box(minx, miny, maxx, maxy))
