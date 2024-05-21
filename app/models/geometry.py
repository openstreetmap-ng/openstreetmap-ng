from typing import Annotated

import numpy as np
from annotated_types import Interval
from shapely import MultiPolygon, Point, Polygon, lib
from shapely.geometry.base import BaseGeometry
from shapely.io import DecodingErrorOptions
from sqlalchemy import BindParameter
from sqlalchemy.sql import func
from sqlalchemy.types import UserDefinedType

from app.validators.geometry import GeometryValidator

Geometry = Annotated[BaseGeometry, GeometryValidator]
PointGeometry = Annotated[Point, GeometryValidator]
PolygonGeometry = Annotated[Polygon, GeometryValidator]
MultiPolygonGeometry = Annotated[Polygon | MultiPolygon, GeometryValidator]
Longitude = Annotated[float, Interval(ge=-180, le=180)]
Latitude = Annotated[float, Interval(ge=-90, le=90)]
Zoom = Annotated[int, Interval(ge=0, le=25)]
# TODO: test if type matches after validation

_invalid_handler = np.uint8(DecodingErrorOptions.get_value('raise'))


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
            x, y = lib.get_coordinates(np.asarray(value, dtype=object), False, False)[0]
            return f'POINT({x} {y})'  # WKT

        return process

    def column_expression(self, col):
        return func.ST_AsBinary(col, type_=self)

    def result_processor(self, dialect, coltype):
        def process(value: bytes | None):
            if value is None:
                return None
            return lib.from_wkb(np.asarray(value, dtype=object), _invalid_handler)

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
            return lib.from_wkb(np.asarray(value, dtype=object), _invalid_handler)

        return process
