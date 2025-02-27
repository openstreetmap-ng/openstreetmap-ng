from collections.abc import Iterable

import cython
import numpy as np
from shapely import Point, lib

from app.models.db.element import Element
from app.models.element import TypedElementId, split_typed_element_id


class Element07Mixin:
    @staticmethod
    def encode_element(element: Element) -> dict:
        return _encode_element(element)

    @staticmethod
    def encode_elements(elements: Iterable[Element]) -> list[dict]:
        return [_encode_element(element) for element in elements]


@cython.cfunc
def _encode_element(element: Element) -> dict:
    type, id = split_typed_element_id(element['typed_id'])
    visible = element['visible']
    result: dict = {
        'type': type,
        'id': id,
        'version': element['version'],
        'user_id': element['user_id'],  # pyright: ignore [reportTypedDictNotRequiredAccess]
        'changeset_id': element['changeset_id'],
        'created_at': element['created_at'],
        'visible': visible,
    }
    if not visible:
        return result

    result['tags'] = element['tags']

    if type == 'node':
        point = element['point']
        assert point is not None, 'point must be set for visible nodes'
        result['point'] = _encode_point(point)
    else:
        members = element['members']
        assert members is not None, 'members must be set for visible ways/relations'
        result['members'] = _encode_members(members, element['members_roles'])

    return result


@cython.cfunc
def _encode_members(members: Iterable[TypedElementId], members_roles: Iterable[str] | None) -> list[dict]:
    result: list[dict] = []
    if members_roles is None:
        # ways
        for member in members:
            type, id = split_typed_element_id(member)
            result.append({'type': type, 'id': id})
    else:
        # relations
        for member, role in zip(members, members_roles, strict=True):
            type, id = split_typed_element_id(member)
            result.append({'type': type, 'id': id, 'role': role})
    return result


@cython.cfunc
def _encode_point(point: Point) -> dict:
    """
    >>> _encode_point(Point(1, 2))
    {'lon': 1, 'lat': 2}
    """
    x, y = lib.get_coordinates(np.asarray(point, dtype=np.object_), False, False)[0].tolist()
    return {'lon': x, 'lat': y}
