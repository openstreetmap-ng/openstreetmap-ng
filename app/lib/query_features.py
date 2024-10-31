from collections.abc import Sequence
from typing import NamedTuple

from shapely import Point

from app.lib.feature_icon import FeatureIcon
from app.models.db.element import Element


class QueryFeatureResult(NamedTuple):
    element: Element
    icon: FeatureIcon | None
    prefix: str
    display_name: str | None
    geoms: Sequence[Point | Sequence[tuple[float, float]]]
