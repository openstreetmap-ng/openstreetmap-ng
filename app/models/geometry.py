from typing import Annotated

from annotated_types import Interval
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry

from app.validators.geometry import GeometryValidator

Geometry = Annotated[BaseGeometry, GeometryValidator]
PointGeometry = Annotated[Point, GeometryValidator]
PolygonGeometry = Annotated[Polygon, GeometryValidator]
MultiPolygonGeometry = Annotated[Polygon | MultiPolygon, GeometryValidator]
Longitude = Annotated[float, Interval(ge=-180, le=180)]
Latitude = Annotated[float, Interval(ge=-90, le=90)]
Zoom = Annotated[int, Interval(ge=0, le=25)]

# TODO: check if type matches after validation
