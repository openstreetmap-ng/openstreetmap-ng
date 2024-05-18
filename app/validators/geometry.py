import numpy as np
from pydantic import PlainValidator
from shapely import Point, lib
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.lib.exceptions_context import raise_for
from app.limits import GEO_COORDINATE_PRECISION


def validate_geometry(value: dict | BaseGeometry) -> BaseGeometry:
    """
    Validate a geometry.
    """
    if isinstance(value, dict):
        value = shape(value)
    if not value.is_valid:
        raise_for().bad_geometry()

    coords: np.ndarray = lib.get_coordinates(np.asarray(value, dtype=object), False, False)

    if not np.all(
        (coords[:, 0] >= -180)
        & (coords[:, 0] <= 180)  #
        & (coords[:, 1] >= -90)
        & (coords[:, 1] <= 90)
    ):
        raise_for().bad_geometry_coordinates()
    return value


def validate_point_precision(value: Point) -> Point:
    """
    Validate a point precision.

    >>> validate_point_precision(Point(0.123456789, 0.123456789))
    Point(0.1234567, 0.1234567)
    """
    coords: np.ndarray = lib.get_coordinates(np.asarray(value, dtype=object), False, False)[0]
    coords = coords.round(GEO_COORDINATE_PRECISION)
    return lib.points(coords)


GeometryValidator = PlainValidator(validate_geometry)
PointPrecisionValidator = PlainValidator(validate_point_precision)
