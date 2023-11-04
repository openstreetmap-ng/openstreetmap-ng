from pydantic import PlainSerializer
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry


def _serialize(value: BaseGeometry) -> dict:
    return mapping(value)


GeometrySerializer = PlainSerializer(_serialize)
