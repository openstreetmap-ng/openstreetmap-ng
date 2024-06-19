from typing import NamedTuple

from shapely import Point, Polygon

from app.models.db.element import Element


class NominatimResult(NamedTuple):
    element: Element
    rank: int
    importance: float
    prefix: str
    display_name: str
    point: Point
    bounds: Polygon
