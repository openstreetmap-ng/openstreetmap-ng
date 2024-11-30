from abc import ABC
from typing import Annotated, override

import numpy as np
from annotated_types import Interval
from shapely import MultiPolygon, Point, Polygon, lib
from shapely.geometry.base import BaseGeometry
from shapely.io import DecodingErrorOptions, WKBFlavorOptions
from sqlalchemy import BindParameter
from sqlalchemy.sql import func
from sqlalchemy.types import UserDefinedType

from app.lib.compressible_geometry import compressible_geometry
from app.limits import GEO_COORDINATE_PRECISION
from app.validators.geometry import GeometryValidator

Geometry = Annotated[BaseGeometry, GeometryValidator]
PointGeometry = Annotated[Point, GeometryValidator]
PolygonGeometry = Annotated[Polygon, GeometryValidator]
MultiPolygonGeometry = Annotated[Polygon | MultiPolygon, GeometryValidator]
Longitude = Annotated[float, Interval(ge=-180, le=180)]
Latitude = Annotated[float, Interval(ge=-90, le=90)]
Zoom = Annotated[int, Interval(ge=0, le=25)]
# TODO: test if type matches after validation

__all__ = (
    'Geometry',
    'Latitude',
    'Longitude',
    'MultiPolygonGeometry',
    'PointGeometry',
    'PolygonGeometry',
    'Zoom',
)


class _GeometryType(UserDefinedType, ABC):
    geometry_type: str

    def get_col_spec(self, **kw):
        return f'geometry({self.geometry_type}, 4326)'

    @override
    def bind_processor(self, dialect):
        wkb_hex = np.False_
        wkb_output_dimensions = np.intc(2)
        wkb_byte_order = np.intc(-1)
        wkb_include_srid = np.False_
        wkb_flavor = np.intc(WKBFlavorOptions.iso.value)

        def process(value: BaseGeometry | None):
            if value is None:
                return None
            return lib.to_wkb(
                compressible_geometry(value),
                wkb_hex,
                wkb_output_dimensions,
                wkb_byte_order,
                wkb_include_srid,
                wkb_flavor,
            )

        return process

    @override
    def bind_expression(self, bindvalue: BindParameter):
        return func.ST_GeomFromWKB(bindvalue, 4326, type_=self)

    @override
    def column_expression(self, colexpr):
        return func.ST_AsBinary(colexpr, type_=self)

    @override
    def result_processor(self, dialect, coltype):
        invalid_handler = np.uint8(DecodingErrorOptions.get_value('raise'))

        def process(value: bytes | None):
            if value is None:
                return None
            geom = lib.from_wkb(np.asarray(value, dtype=np.object_), invalid_handler)
            geoms = np.asarray(geom, dtype=np.object_)
            return lib.set_coordinates(
                geoms,
                lib.get_coordinates(geoms, False, False).round(GEO_COORDINATE_PRECISION),
            ).tolist()

        return process


class PointType(_GeometryType):
    geometry_type = 'Point'
    cache_ok = True


class PolygonType(_GeometryType):
    geometry_type = 'Polygon'
    cache_ok = True


class MultiPointType(_GeometryType):
    geometry_type = 'MultiPoint'
    cache_ok = True
