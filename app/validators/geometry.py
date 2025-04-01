from typing import Any, TypeVar, overload

import numpy as np
from pydantic import BeforeValidator
from shapely import MultiPolygon, Point, Polygon, buffer, get_coordinates, set_srid
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.config import GEO_COORDINATE_PRECISION
from app.lib.exceptions_context import raise_for

_T = TypeVar('_T', bound=BaseGeometry)


@overload
def validate_geometry(value: dict[str, Any]) -> BaseGeometry: ...
@overload
def validate_geometry(value: _T) -> _T: ...
def validate_geometry(value: dict[str, Any] | _T) -> BaseGeometry | _T:
    """Validate a geometry."""
    geom: BaseGeometry = shape(value) if isinstance(value, dict) else value
    coords = get_coordinates(geom)
    if not np.all(
        (coords[:, 0] >= -180)
        & (coords[:, 0] <= 180)  #
        & (coords[:, 1] >= -90)
        & (coords[:, 1] <= 90)
    ):
        raise_for.bad_geometry_coordinates()

    # Optimized validation for points
    if isinstance(geom, Point):
        if coords.shape != (1, 2):
            raise_for.bad_geometry()

    # Validate the geometry but accept zero-sized polygons
    elif not geom.is_valid:
        if isinstance(geom, Polygon | MultiPolygon) and not geom.length:
            geom = buffer(geom, 0.1**GEO_COORDINATE_PRECISION / 4, 0)
        else:
            raise_for.bad_geometry()

    return set_srid(geom, 4326)


GeometryValidator = BeforeValidator(validate_geometry)
