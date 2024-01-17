from geoalchemy2 import Geometry, WKBElement
from geoalchemy2.shape import from_shape, to_shape
from shapely import Point, Polygon
from sqlalchemy import Dialect, TypeDecorator

from app.config import SRID


class PointType(TypeDecorator):
    impl = Geometry(geometry_type='POINT', srid=SRID, spatial_index=False)
    cache_ok = True

    def process_bind_param(self, value: Point | None, _: Dialect) -> WKBElement | None:
        if value is None:
            return None
        return from_shape(value, srid=SRID)

    def process_result_value(self, value: WKBElement | None, _: Dialect) -> Point | None:
        if value is None:
            return None
        return to_shape(value)


class PolygonType(TypeDecorator):
    impl = Geometry(geometry_type='POLYGON', srid=SRID, spatial_index=False)
    cache_ok = True

    def process_bind_param(self, value: Polygon | None, _: Dialect) -> WKBElement | None:
        if value is None:
            return None
        return from_shape(value, srid=SRID)

    def process_result_value(self, value: WKBElement | None, _: Dialect) -> Polygon | None:
        if value is None:
            return None
        return to_shape(value)
