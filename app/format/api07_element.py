import cython
from shapely import Point, get_coordinates

from app.models.db.element import Element
from app.models.element import TypedElementId, split_typed_element_id, split_typed_element_ids


class Element07Mixin:
    @staticmethod
    def encode_element(element: Element) -> dict:
        return _encode_element(element)

    @staticmethod
    def encode_elements(elements: list[Element]) -> list[dict]:
        return [_encode_element(element) for element in elements]


@cython.cfunc
def _encode_element(element: Element) -> dict:
    type, id = split_typed_element_id(element['typed_id'])
    visible = element['visible']
    result = {
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
def _encode_members(members: list[TypedElementId], members_roles: list[str] | None) -> list[dict]:
    if members_roles is None:
        # Ways
        return [
            {'type': type, 'id': id}  #
            for type, id in split_typed_element_ids(members)
        ]
    else:
        # Relations
        return [
            {'type': type, 'id': id, 'role': role}
            for (type, id), role in zip(
                split_typed_element_ids(members),
                members_roles,
                strict=True,
            )
        ]


@cython.cfunc
def _encode_point(point: Point) -> dict:
    """
    >>> _encode_point(Point(1, 2))
    {'lon': 1, 'lat': 2}
    """
    x, y = get_coordinates(point)[0].tolist()
    return {'lon': x, 'lat': y}
