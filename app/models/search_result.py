from dataclasses import dataclass

from shapely import Point, Polygon

from app.models.db.element import Element


@dataclass(kw_only=True, slots=True)
class SearchResult:
    element: Element
    rank: int  # for determining global vs local relevance
    importance: float  # for sorting results
    prefix: str
    display_name: str
    point: Point | None
    bounds: Polygon
