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


class ChangesetLeaflet(msgspec.Struct):
    id: int
    geom: list[float]  # [minLon, minLat, maxLon, maxLat]
    user: str | None
    closed: bool
    timeago: str
    num_comments: int


class NoteLeaflet(msgspec.Struct):
    id: int
    geom: list[float]  # [lat, lon]
    text: str
    open: bool
