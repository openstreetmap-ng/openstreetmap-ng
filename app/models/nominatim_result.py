from dataclasses import dataclass

from shapely import Point, Polygon

from app.models.db.element import Element


@dataclass(kw_only=True, slots=True)
class NominatimResult:
    element: Element
    rank: int
    importance: float
    prefix: str
    display_name: str
    point: Point | None
    bounds: Polygon
