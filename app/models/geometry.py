from typing import Annotated

from annotated_types import Interval
from shapely import MultiPolygon, Point, Polygon, from_wkb, get_coordinates
from shapely.geometry.base import BaseGeometry
from sqlalchemy import BindParameter
from sqlalchemy.sql import func
from sqlalchemy.types import UserDefinedType

from app.validators.geometry import GeometryValidator, PointPrecisionValidator

Geometry = Annotated[BaseGeometry, GeometryValidator]
PointGeometry = Annotated[Point, GeometryValidator]
PointPrecisionGeometry = Annotated[Point, GeometryValidator, PointPrecisionValidator]
PolygonGeometry = Annotated[Polygon, GeometryValidator]
MultiPolygonGeometry = Annotated[Polygon | MultiPolygon, GeometryValidator]
Longitude = Annotated[float, Interval(ge=-180, le=180)]
Latitude = Annotated[float, Interval(ge=-90, le=90)]
Zoom = Annotated[int, Interval(ge=0, le=25)]
# TODO: test if type matches after validation


class PointType(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return 'geometry(Point, 4326)'

    def bind_expression(self, bindvalue: BindParameter):
        return func.ST_GeomFromText(bindvalue, 4326, type_=self)

    def bind_processor(self, dialect):
        def process(value: Point | None):
            if value is None:
                return None
            x, y = get_coordinates(value)[0]
            return f'POINT({x} {y})'  # WKT

        return process

    def column_expression(self, col):
        return func.ST_AsBinary(col, type_=self)

    def result_processor(self, dialect, coltype):
        def process(value: bytes | None):
            if value is None:
                return None
            return from_wkb(value)

        return process


class PolygonType(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return 'geometry(Polygon, 4326)'

    def bind_expression(self, bindvalue: BindParameter):
        return func.ST_GeomFromText(bindvalue, 4326, type_=self)

    def bind_processor(self, dialect):
        def process(value: Polygon | None):
            if value is None:
                return None
            return value.wkt

        return process

    def column_expression(self, col):
        return func.ST_AsBinary(col, type_=self)

    def result_processor(self, dialect, coltype):
        def process(value: bytes | None):
            if value is None:
                return None
            return from_wkb(value)

        return process
