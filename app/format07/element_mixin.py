from collections.abc import Sequence

import cython
from shapely import Point, get_coordinates

from app.models.db.element import Element
from app.models.element_member_ref import ElementMemberRef


class Element07Mixin:
    @staticmethod
    def encode_element(element: Element) -> dict:
        return _encode_element(element)

    @staticmethod
    def encode_elements(elements: Sequence[Element]) -> Sequence[dict]:
        return tuple(_encode_element(element) for element in elements)


@cython.cfunc
def _encode_members(members: Sequence[ElementMemberRef]) -> tuple[dict, ...]:
    return tuple(
        {
            'type': member.type,
            'id': member.id,
            'role': member.role,
        }
        for member in members
    )


@cython.cfunc
def _encode_element(element: Element) -> dict:
    return {
        'type': element.type,
        'id': element.id,
        'version': element.version,
        'user_id': element.changeset.user_id,
        'changeset_id': element.changeset_id,
        'created_at': element.created_at,
        'visible': element.visible,
        **(_encode_point(element.point) if (element.point is not None) else {}),
        'tags': element.tags,
        'members': _encode_members(element.members),
    }


@cython.cfunc
def _encode_point(point: Point | None) -> dict:
    """
    >>> _encode_point(Point(1, 2))
    {'lon': 1, 'lat': 2}
    """
    if point is None:
        return {}

    x, y = get_coordinates(point)[0].tolist()
    return {'lon': x, 'lat': y}
