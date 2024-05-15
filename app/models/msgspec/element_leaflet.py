import msgspec

from app.models.element_type import ElementType


class ElementLeaflet(msgspec.Struct):
    type: ElementType
    id: int


class ElementLeafletNode(ElementLeaflet):
    geom: tuple[float, float]  # (lon, lat)


class ElementLeafletWay(ElementLeaflet):
    geom: list[float]  # [lon1, lat1, lon2, lat2, ...]
    area: bool
