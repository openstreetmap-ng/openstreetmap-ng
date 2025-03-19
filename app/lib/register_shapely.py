from typing import override

from psycopg import postgres
from psycopg._typeinfo import TypeInfo
from psycopg.abc import AdaptContext, Buffer
from psycopg.adapt import Dumper, Loader
from psycopg.pq import Format
from shapely import from_wkb, to_wkb
from shapely.geometry.base import BaseGeometry


class GeometryBinaryLoader(Loader):
    format = Format.BINARY

    @override
    def load(self, data: Buffer) -> BaseGeometry:
        return from_wkb(bytes(data))


class GeometryLoader(Loader):
    @override
    def load(self, data: Buffer) -> BaseGeometry:
        # it's a hex string in binary
        return from_wkb(bytes(data))


class BaseGeometryBinaryDumper(Dumper):
    format = Format.BINARY

    @override
    def dump(self, obj: BaseGeometry) -> Buffer:
        return to_wkb(obj, include_srid=True)


class BaseGeometryDumper(Dumper):
    @override
    def dump(self, obj: BaseGeometry) -> Buffer:
        return to_wkb(obj, True, include_srid=True).encode()


def register_shapely(info: TypeInfo, context: AdaptContext | None = None) -> None:
    """Register Shapely dumper and loaders."""
    info.register(context)
    adapters = context.adapters if context else postgres.adapters

    adapters.register_loader(info.oid, GeometryBinaryLoader)
    adapters.register_loader(info.oid, GeometryLoader)
    # Default binary dump
    adapters.register_dumper(BaseGeometry, _make_dumper(info.oid))
    adapters.register_dumper(BaseGeometry, _make_binary_dumper(info.oid))


def _make_dumper(oid_in: int) -> type[BaseGeometryDumper]:
    class GeometryDumper(BaseGeometryDumper):
        oid = oid_in

    return GeometryDumper


def _make_binary_dumper(oid_in: int) -> type[BaseGeometryBinaryDumper]:
    class GeometryBinaryDumper(BaseGeometryBinaryDumper):
        oid = oid_in

    return GeometryBinaryDumper
