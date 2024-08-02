from collections.abc import Collection

import msgspec

from app.models.element import ElementType


class ElementLeaflet(msgspec.Struct):
    type: ElementType
    id: int


class ElementLeafletNode(ElementLeaflet):
    geom: Collection[float]  # [lat, lon]


class ElementLeafletWay(ElementLeaflet):
    geom: Collection[Collection[float]]  # [[lat, lon], ...]
    area: bool


class ChangesetLeaflet(msgspec.Struct):
    id: int
    geom: Collection[Collection[float]]  # [[minLon, minLat, maxLon, maxLat], ...]
    user_name: str | None
    user_avatar: str | None
    closed: bool
    timeago: str
    comment: str | None
    num_comments: int


class NoteLeaflet(msgspec.Struct):
    id: int
    geom: Collection[float]  # [lat, lon]
    text: str
    open: bool
