from collections import defaultdict
from collections.abc import Collection, Iterable, Sequence
from typing import Any

import cython
import numpy as np
from shapely import Point, lib

from app.lib.date_utils import legacy_date
from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_json
from app.limits import GEO_COORDINATE_PRECISION
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.element import ElementType
from app.models.validating.element import ElementValidating
from app.services.optimistic_diff.prepare import OSMChangeAction


class Element06Mixin:
    @staticmethod
    def encode_element(element: Element) -> dict:
        """
        >>> encode_element(Element(type='node', id=1, version=1, ...))
        {'node': {'@id': 1, '@version': 1, ...}}
        """
        if format_is_json():
            return _encode_element(element, is_json=True)
        else:
            return {element.type: _encode_element(element, is_json=False)}

    @staticmethod
    def encode_elements(elements: Iterable[Element]) -> dict[str, Sequence[dict]]:
        """
        >>> encode_elements([
        ...     Element(type='node', id=1, version=1, ...),
        ...     Element(type=ElementType.way, id=2, version=1,
        ... ])
        {'node': [{'@id': 1, '@version': 1, ...}], 'way': [{'@id': 2, '@version': 1, ...}]}
        """
        if format_is_json():
            return {'elements': tuple(_encode_element(element, is_json=True) for element in elements)}
        else:
            result: dict[ElementType, list[dict]] = defaultdict(list)
            # merge elements of the same type together
            for element in elements:
                result[element.type].append(_encode_element(element, is_json=False))
            return result  # pyright: ignore[reportReturnType]

    @staticmethod
    def decode_element(element: tuple[ElementType, dict]) -> Element:
        """
        >>> decode_element(('node', {'@id': 1, '@version': 1, ...}))
        Element(type='node', ...)
        """
        type = element[0]
        data = element[1]
        return _decode_element(type, data, changeset_id=None)

    @staticmethod
    def encode_osmchange(elements: Collection[Element]) -> list[tuple[OSMChangeAction, dict[ElementType, dict]]]:
        """
        >>> encode_osmchange([
        ...     Element(type='node', id=1, version=1, ...),
        ...     Element(type=ElementType.way, id=2, version=2, ...)
        ... ])
        [
            ('create', {'node': {'@id': 1, '@version': 1, ...}}),
            ('modify', {'way': {'@id': 2, '@version': 2, ...}}),
        ]
        """
        result: list[tuple[OSMChangeAction, dict[ElementType, dict]]] = [None] * len(elements)  # pyright: ignore[reportAssignmentType]
        action: OSMChangeAction
        i: cython.int
        for i, element in enumerate(elements):
            # determine the action automatically
            if element.version == 1:
                action = 'create'
            elif element.visible:
                action = 'modify'
            else:
                action = 'delete'
            result_: tuple[OSMChangeAction, dict[ElementType, dict]]
            result_ = (action, {element.type: _encode_element(element, is_json=False)})
            result[i] = result_
        return result

    @staticmethod
    def decode_osmchange(
        changes: Iterable[tuple[OSMChangeAction, Iterable[tuple[ElementType, dict]]]],
        *,
        changeset_id: int | None,
    ) -> list[Element]:
        """
        If changeset_id is None, it will be extracted from the element data.

        >>> decode_osmchange([
        ...     ('create', [('node', {'@id': 1, '@version': 1, ...})]),
        ...     ('modify', [('way', {'@id': 2, '@version': 2, ...})])
        ... ])
        [Element(type=ElementType, ...), Element(type=ElementType.way, ...)]
        """
        # skip attributes-only osmChange
        if isinstance(changes, dict):
            return []

        result = []
        for action, elements_data in changes:
            # skip osmChange attributes
            if action.startswith('@'):
                continue
            # skip attributes-only actions
            if isinstance(elements_data, dict):
                continue

            if action == 'create':
                for key, data in elements_data:
                    data['@version'] = 0
                    element = _decode_element(key, data, changeset_id=changeset_id)

                    if element.id > 0:
                        raise_for().diff_create_bad_id(element)

                    result.append(element)

            elif action == 'modify':
                for key, data in elements_data:
                    element = _decode_element(key, data, changeset_id=changeset_id)

                    if element.version <= 1:
                        raise_for().diff_update_bad_version(element)

                    result.append(element)

            elif action == 'delete':
                delete_if_unused: cython.char = False

                for key, data in elements_data:
                    if key == '@if-unused':  # pyright: ignore[reportUnnecessaryComparison]
                        delete_if_unused = True
                        continue

                    data['@visible'] = False
                    element = _decode_element(key, data, changeset_id=changeset_id)

                    if element.version <= 1:
                        raise_for().diff_update_bad_version(element)
                    if delete_if_unused:
                        element.delete_if_unused = True

                    result.append(element)

            else:
                raise_for().diff_unsupported_action(action)

        return result


@cython.cfunc
def _encode_nodes_json(nodes: Iterable[ElementMember]) -> tuple[int, ...]:
    """
    >>> _encode_nodes_json([
    ...     ElementMember(type='node', id=1, role=''),
    ...     ElementMember(type='node', id=2, role=''),
    ... ])
    (1, 2)
    """
    return tuple(node.id for node in nodes)


@cython.cfunc
def _encode_nodes_xml(nodes: Iterable[ElementMember]) -> tuple[dict[str, int], ...]:
    """
    >>> _encode_nodes_xml([
    ...     ElementMember(type='node', id=1, role=''),
    ...     ElementMember(type='node', id=2, role=''),
    ... ])
    ({'@ref': 1}, {'@ref': 2})
    """
    return tuple({'@ref': node.id} for node in nodes)


@cython.cfunc
def _decode_nodes(nodes: Iterable[dict]) -> tuple[ElementMember, ...]:
    """
    >>> _decode_nodes([{'@ref': '1'}])
    [ElementMember(type='node', id=1, role='')]
    """
    return tuple(
        ElementMember(
            order=i,
            type='node',
            id=int(node['@ref']),  # pyright: ignore[reportArgumentType]
            role='',
        )
        for i, node in enumerate(nodes)
    )


@cython.cfunc
def _encode_members_json(members: Iterable[ElementMember]) -> tuple[dict[str, Any], ...]:
    """
    >>> _encode_members_json([
    ...     ElementMember(type='node', id=1, role='a'),
    ...     ElementMember(type='way', id=2, role='b'),
    ... ])
    [
        {'type': 'node', 'ref': 1, 'role': 'a'},
        {'type': 'way', 'ref': 2, 'role': 'b'},
    ]
    """
    return tuple({'type': member.type, 'ref': member.id, 'role': member.role} for member in members)


@cython.cfunc
def _encode_members_xml(members: Iterable[ElementMember]) -> tuple[dict[str, Any], ...]:
    """
    >>> _encode_members_xml([
    ...     ElementMember(type='node', id=1, role='a'),
    ...     ElementMember(type='way', id=2, role='b'),
    ... ])
    [
        {'@type': 'node', '@ref': 1, '@role': 'a'},
        {'@type': 'way', '@ref': 2, '@role': 'b'},
    ]
    """
    return tuple({'@type': member.type, '@ref': member.id, '@role': member.role} for member in members)


# TODO: validate role length
# TODO: validate type
@cython.cfunc
def _decode_members_unsafe(members: Iterable[dict]) -> tuple[ElementMember, ...]:
    """
    This method does not validate the input data.

    >>> _decode_members_unsafe([
    ...     {'@type': 'node', '@ref': '1', '@role': 'a'},
    ... ])
    [ElementMember(type='node', id=1, role='a')]
    """
    return tuple(
        ElementMember(
            order=i,
            type=member['@type'],
            id=int(member['@ref']),  # pyright: ignore[reportArgumentType]
            role=member['@role'],
        )
        for i, member in enumerate(members)
    )


@cython.cfunc
def _encode_element(element: Element, *, is_json: cython.char) -> dict:
    """
    >>> _encode_element(Element(type='node', id=1, version=1, ...))
    {'@id': 1, '@version': 1, ...}
    """
    # read property once for performance
    element_type = element.type
    is_node: cython.char = element_type == 'node'
    is_way: cython.char = not is_node and element_type == 'way'
    is_relation: cython.char = not is_node and not is_way

    if is_json:
        return {
            'type': element_type,
            'id': element.id,
            'version': element.version,
            **(
                {
                    'uid': element.user_id,
                    'user': element.user_display_name,
                }
                if element.user_display_name is not None
                else {}
            ),
            'changeset': element.changeset_id,
            'timestamp': legacy_date(element.created_at),
            'visible': element.visible,
            **(_encode_point_json(element.point) if is_node else {}),
            'tags': element.tags,
            **({'nodes': _encode_nodes_json(element.members)} if is_way else {}),  # pyright: ignore[reportArgumentType]
            **({'members': _encode_members_json(element.members)} if is_relation else {}),  # pyright: ignore[reportArgumentType]
        }
    else:
        return {
            '@id': element.id,
            '@version': element.version,
            **(
                {
                    '@uid': element.user_id,
                    '@user': element.user_display_name,
                }
                if element.user_display_name is not None
                else {}
            ),
            '@changeset': element.changeset_id,
            '@timestamp': legacy_date(element.created_at),
            '@visible': element.visible,
            **(_encode_point_xml(element.point) if is_node else {}),
            'tag': tuple({'@k': k, '@v': v} for k, v in element.tags.items()),
            **({'nd': _encode_nodes_xml(element.members)} if is_way else {}),  # pyright: ignore[reportArgumentType]
            **({'member': _encode_members_xml(element.members)} if is_relation else {}),  # pyright: ignore[reportArgumentType]
        }


@cython.cfunc
def _decode_element(type: ElementType, data: dict, *, changeset_id: int | None):
    """
    If changeset_id is None, it will be extracted from the element data.

    >>> decode_element(('node', {'@id': 1, '@version': 1, ...}))
    Element(type='node', ...)
    """
    if (data_tags := data.get('tag')) is not None:
        tags = _decode_tags_unsafe(data_tags)
    else:
        tags = {}

    if (lon := data.get('@lon')) is None or (lat := data.get('@lat')) is None:
        point = None
    else:
        # numpy automatically parses strings
        coordinate_precision = GEO_COORDINATE_PRECISION
        point = lib.points(np.array((lon, lat), np.float64).round(coordinate_precision))

    # decode members from either nd or member
    if type == 'way' and (data_nodes := data.get('nd')) is not None:
        members = _decode_nodes(data_nodes)
    elif type == 'relation' and (data_members := data.get('member')) is not None:
        members = _decode_members_unsafe(data_members)
    else:
        members = ()

    return Element(
        **ElementValidating(
            changeset_id=changeset_id if (changeset_id is not None) else data.get('@changeset'),
            type=type,
            id=data.get('@id'),  # pyright: ignore[reportArgumentType]
            version=data.get('@version', 0) + 1,
            visible=data.get('@visible', True),
            tags=tags,
            point=point,
            members=members,
        ).__dict__
    )


@cython.cfunc
def _encode_point_json(point: Point | None) -> dict[str, float]:
    """
    >>> _encode_point_json(Point(1, 2))
    {'lon': 1, 'lat': 2}
    """
    if point is None:
        return {}
    x, y = lib.get_coordinates(np.asarray(point, dtype=object), False, False)[0].tolist()
    return {'lon': x, 'lat': y}


@cython.cfunc
def _encode_point_xml(point: Point | None) -> dict[str, float]:
    """
    >>> _encode_point_xml(Point(1, 2))
    {'@lon': 1, '@lat': 2}
    """
    if point is None:
        return {}
    x, y = lib.get_coordinates(np.asarray(point, dtype=object), False, False)[0].tolist()
    return {'@lon': x, '@lat': y}


@cython.cfunc
def _decode_tags_unsafe(tags: Iterable[dict]) -> dict:
    """
    This method does not validate the input data.

    >>> _decode_tags_unsafe([
    ...     {'@k': 'a', '@v': '1'},
    ...     {'@k': 'b', '@v': '2'},
    ... ])
    {'a': '1', 'b': '2'}
    """
    items = tuple((tag['@k'], tag['@v']) for tag in tags)
    result = dict(items)
    if len(items) != len(result):
        raise ValueError('Duplicate tag keys')
    return result
