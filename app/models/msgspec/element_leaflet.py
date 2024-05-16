import msgspec

from app.models.element_type import ElementType


class ElementLeaflet(msgspec.Struct):
    type: ElementType
    id: int


class ElementLeafletNode(ElementLeaflet):
    geom: list[float]  # [lat, lon]


class ElementLeafletWay(ElementLeaflet):
    geom: list[list[float]]  # [[lat, lon], ...]
    area: bool
