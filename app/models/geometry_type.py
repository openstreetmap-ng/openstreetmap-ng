from shapely import Point, Polygon, from_wkb, get_coordinates
from sqlalchemy import BindParameter
from sqlalchemy.sql import func
from sqlalchemy.types import UserDefinedType


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
