import cython
from pydantic import PlainValidator
from shapely.geometry import shape
from shapely.ops import BaseGeometry

from app.lib.exceptions_context import raise_for


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
    geom_type: str = geom.geom_type

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


GeometryValidator = PlainValidator(validate_geometry)
