from typing import NamedTuple

from shapely.geometry import Point, Polygon


class NominatimResult(NamedTuple):
    point: Point
    name: str
    bounds: Polygon
