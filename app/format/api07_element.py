from collections.abc import Iterable

import cython
import numpy as np
from shapely import Point, lib

from app.models.db.element import Element
from app.models.db.element_member import ElementMember


class Element07Mixin:
    @staticmethod
    def encode_element(element: Element) -> dict:
        return _encode_element(element)

    @staticmethod
    def encode_elements(elements: Iterable[Element]) -> tuple[dict, ...]:
        return tuple(_encode_element(element) for element in elements)


@cython.cfunc
def _encode_members(members: Iterable[ElementMember]) -> tuple[dict, ...]:
    return tuple({'type': member.type, 'id': member.id, 'role': member.role} for member in members)


@cython.cfunc
def _encode_element(element: Element) -> dict:
    element_members = element.members
    if element_members is None:
        raise AssertionError('Element members must be set')
    return {
        'type': element.type,
        'id': element.id,
        'version': element.version,
        'user_id': element.user_id,
        'changeset_id': element.changeset_id,
        'created_at': element.created_at,
        'visible': element.visible,
        **(_encode_point(element.point) if (element.point is not None) else {}),
        'tags': element.tags,
        'members': _encode_members(element_members),
    }


@cython.cfunc
def _encode_point(point: Point | None) -> dict:
    """
    >>> _encode_point(Point(1, 2))
    {'lon': 1, 'lat': 2}
    """
    if point is None:
        return {}
    x, y = lib.get_coordinates(np.asarray(point, dtype=np.object_), False, False)[0].tolist()
    return {'lon': x, 'lat': y}
