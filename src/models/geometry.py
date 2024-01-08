from typing import Annotated

from annotated_types import Interval
from pydantic import AllowInfNan
from serializers.geometry import GeometrySerializer
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry

from src.validators.geometry import GeometryValidator

Geometry = Annotated[
    BaseGeometry,
    GeometryValidator,
    GeometrySerializer,
]

PointGeometry = Annotated[
    Point,
    GeometryValidator,
    GeometrySerializer,
]

PolygonGeometry = Annotated[
    Polygon,
    GeometryValidator,
    GeometrySerializer,
]

MultiPolygonGeometry = Annotated[
    Polygon | MultiPolygon,
    GeometryValidator,
    GeometrySerializer,
]

Longitude = Annotated[float, Interval(ge=-180, le=180), AllowInfNan(False)]

Latitude = Annotated[float, Interval(ge=-90, le=90), AllowInfNan(False)]

# TODO: check if type matches after validation
