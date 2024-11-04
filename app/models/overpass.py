from typing import Literal, NotRequired, TypedDict

from app.models.element import ElementId

# Overpass API Documentation:
# https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL


class _OverpassPoint(TypedDict):
    lat: float
    lon: float


class _OverpassBounds(TypedDict):
    minlat: float
    minlon: float
    maxlat: float
    maxlon: float


class _OverpassElement(TypedDict):
    id: ElementId
    tags: NotRequired[dict[str, str]]


class OverpassNode(_OverpassElement):
    type: Literal[Literal['node']]
    lat: float
    lon: float


class OverpassWay(_OverpassElement):
    type: Literal[Literal['way']]
    nodes: list[ElementId]
    bounds: _OverpassBounds
    geometry: list[_OverpassPoint]


class _OverpassElementMember(TypedDict):
    ref: ElementId
    role: str


class OverpassNodeMember(_OverpassElementMember):
    type: Literal['node']
    lat: float
    lon: float


class OverpassWayMember(_OverpassElementMember):
    type: Literal['way']
    geometry: list[_OverpassPoint]


class OverpassRelationMember(_OverpassElementMember):
    type: Literal['relation']


class OverpassRelation(_OverpassElement):
    type: Literal[Literal['relation']]
    bounds: _OverpassBounds
    members: list['OverpassElementMember']


OverpassElement = OverpassNode | OverpassWay | OverpassRelation
OverpassElementMember = OverpassNodeMember | OverpassWayMember | OverpassRelationMember

__all__ = (
    'OverpassElement',
    'OverpassElementMember',
)
