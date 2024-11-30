from typing import Any, TypeVar, overload

import numpy as np
from pydantic import PlainValidator
from shapely import Point, lib
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.lib.exceptions_context import raise_for

T = TypeVar('T', bound=BaseGeometry)


@overload
def validate_geometry(value: dict[str, Any]) -> BaseGeometry: ...


@overload
def validate_geometry(value: T) -> T: ...


def validate_geometry(value: dict[str, Any] | T) -> BaseGeometry | T:
    """
    Validate a geometry.
    """
    geom: BaseGeometry = shape(value) if isinstance(value, dict) else value
    coords = lib.get_coordinates(np.asarray(geom, dtype=np.object_), False, False)
    if not np.all(
        (coords[:, 0] >= -180)
        & (coords[:, 0] <= 180)  #
        & (coords[:, 1] >= -90)
        & (coords[:, 1] <= 90)
    ):
        raise_for.bad_geometry_coordinates()

    # optimized validation for points
    if isinstance(geom, Point):
        if coords.shape != (1, 2):
            raise_for.bad_geometry()
    elif not geom.is_valid:
        raise_for.bad_geometry()

    return geom


GeometryValidator = PlainValidator(validate_geometry)
