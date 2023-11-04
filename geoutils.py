from shapely.geometry import Polygon, box, mapping

from lib.exceptions import Exceptions
from validators.geometry import validate_geometry


def mapping_mongo(ob) -> dict:
    '''
    Return a GeoJSON-like mapping from a Geometry.

    Additionally, add a CRS field to the mapping to avoid big polygon issues.
    '''

    result = mapping(ob)
    result['crs'] = {
        'type': 'name',
        'properties': {
            'name': 'urn:x-mongodb:crs:strictwinding:EPSG:4326'
        }
    }
    return result


def parse_bbox(s: str) -> Polygon:
    '''
    Parse a bbox string.

    Raises exception if the string is not a valid bbox format.

    >>> parse_bbox('1,2,3,4')
    POLYGON ((1 2, 1 4, 3 4, 3 2, 1 2))
    '''
    try:
        parts = s.split(',', maxsplit=3)
        minx, miny, maxx, maxy = map(float, (s.strip() for s in parts))
    except Exception:
        Exceptions.get().raise_for_bad_bbox(s)
    if minx > maxx:
        Exceptions.get().raise_for_bad_bbox(s, 'min longitude > max longitude')
    if miny > maxy:
        Exceptions.get().raise_for_bad_bbox(s, 'min latitude > max latitude')
    return validate_geometry(box(minx, miny, maxx, maxy))
