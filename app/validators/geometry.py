import numpy as np
from pydantic import PlainValidator
from shapely import Point, lib
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.lib.exceptions_context import raise_for


def validate_geometry(value: dict | BaseGeometry) -> BaseGeometry:
    """
    Validate a geometry.
    """
    if isinstance(value, dict):
        value = shape(value)

    coords: np.ndarray = lib.get_coordinates(np.asarray(value, dtype=object), False, False)
    if not np.all(
        (coords[:, 0] >= -180)
        & (coords[:, 0] <= 180)  #
        & (coords[:, 1] >= -90)
        & (coords[:, 1] <= 90)
    ):
        raise_for().bad_geometry_coordinates()

    # optimized validation for points
    if isinstance(value, Point):
        if coords.shape != (1, 2):
            raise_for().bad_geometry()
    elif not value.is_valid:
        raise_for().bad_geometry()

    return value


GeometryValidator = PlainValidator(validate_geometry)
