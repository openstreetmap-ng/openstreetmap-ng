from typing import NamedTuple

from shapely.geometry import Point, Polygon


class NominatimSearchGeneric(NamedTuple):
    point: Point
    name: str
    bounds: Polygon
