import numpy as np
from pydantic import PlainValidator
from shapely import get_coordinates
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.lib.exceptions_context import raise_for


def validate_geometry(value: dict | BaseGeometry) -> BaseGeometry:
    """
    Validate a geometry.
    """

    if isinstance(value, dict):
        value = shape(value)

    if not value.is_valid:
        raise_for().bad_geometry()

    coords: np.ndarray = get_coordinates(value)

    if not np.all((coords[:, 0] >= -180) & (coords[:, 0] <= 180) & (coords[:, 1] >= -90) & (coords[:, 1] <= 90)):
        raise_for().bad_geometry_coordinates()

    return value


GeometryValidator = PlainValidator(validate_geometry)
