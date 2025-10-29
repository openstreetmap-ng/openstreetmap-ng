from typing import TypedDict

from shapely.geometry.base import BaseGeometry

from app.models.element import TypedElementId
from app.models.types import SequenceId


class ElementSpatial(TypedDict):
    typed_id: TypedElementId
    sequence_id: SequenceId
    geom: BaseGeometry

    # runtime
    version: int
    tags: dict[str, str] | None
