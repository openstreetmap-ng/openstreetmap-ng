from typing import NamedTuple

from shapely import Point, Polygon


class NominatimResult(NamedTuple):
    point: Point
    name: str
    bounds: Polygon
