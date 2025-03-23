import logging
from typing import Any

import cython
import numpy as np
from shapely import Point, get_coordinates, lib

from app.lib.date_utils import legacy_date
from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_json
from app.limits import GEO_COORDINATE_PRECISION
from app.models.db.element import Element, ElementInit, validate_elements
from app.models.element import (
    ElementId,
    ElementType,
    TypedElementId,
    split_typed_element_id,
    split_typed_element_ids,
    split_typed_element_ids2,
    typed_element_id,
)
from app.models.types import ChangesetId
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

        type = split_typed_element_id(element['typed_id'])[0]
        return {type: _encode_element(element, is_json=False)}

    @staticmethod
    def encode_elements(elements: list[Element]) -> dict[str, list[dict]]:
        """
        >>> encode_elements([
        ...     Element(type='node', id=1, version=1, ...),
        ...     Element(type=ElementType.way, id=2, version=1,
        ... ])
        {'node': [{'@id': 1, '@version': 1, ...}], 'way': [{'@id': 2, '@version': 1, ...}]}
        """
        if format_is_json():
            return {'elements': [_encode_element(element, is_json=True) for element in elements]}

        # Merge elements of the same type together
        result: dict[ElementType, list[dict]] = {'node': [], 'way': [], 'relation': []}
        for element, type_id in zip(
            elements,
            split_typed_element_ids2(elements),
            strict=True,
        ):
            result[type_id[0]].append(_encode_element(element, is_json=False))
        return result  # pyright: ignore[reportReturnType]

    @staticmethod
    def decode_elements(elements: list[tuple[ElementType, dict]]) -> list[ElementInit]:
        """
        >>> decode_elements(('node', {'@id': 1, '@version': 1, ...}))
        Element(type='node', ...)
        """
        return validate_elements([_decode_element_unsafe(type, data, changeset_id=None) for (type, data) in elements])

    @staticmethod
    def encode_osmchange(elements: list[Element]) -> list[tuple[OSMChangeAction, dict[ElementType, dict]]]:
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
        result: list[tuple[OSMChangeAction, dict[ElementType, dict]]] = [None] * len(elements)  # type: ignore
        action: OSMChangeAction

        i: cython.Py_ssize_t
        for i, (element, type_id) in enumerate(
            zip(
                elements,
                split_typed_element_ids2(elements),
                strict=True,
            )
        ):
            # determine the action automatically
            if element['version'] == 1:
                action = 'create'
            elif element['visible']:
                action = 'modify'
            else:
                action = 'delete'

            result_: tuple[OSMChangeAction, dict[ElementType, dict]]
            result_ = (action, {type_id[0]: _encode_element(element, is_json=False)})
            result[i] = result_

        return result

    @staticmethod
    def decode_osmchange(
        changeset_id: ChangesetId | None,
        changes: list[tuple[OSMChangeAction, list[tuple[ElementType, dict]]]] | dict,
    ) -> list[ElementInit]:
        """
        If changeset_id is None, it will be extracted from the element data.

        >>> decode_osmchange([
        ...     ('create', [('node', {'@id': 1, '@version': 1, ...})]),
        ...     ('modify', [('way', {'@id': 2, '@version': 2, ...})])
        ... ])
        [Element(type=ElementType, ...), Element(type=ElementType.way, ...)]
        """
        # skip attributes-only osmChange (empty)
        if isinstance(changes, dict):
            logging.debug('Skipped empty osmChange')
            return []

        result: list[ElementInit] = []
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
                    element = _decode_element_unsafe(key, data, changeset_id=changeset_id)
                    element_id = split_typed_element_id(element['typed_id'])[1]

                    if element_id > 0:
                        raise_for.diff_create_bad_id(element)

                    result.append(element)

            elif action == 'modify':
                for key, data in elements_data:
                    element = _decode_element_unsafe(key, data, changeset_id=changeset_id)

                    if element['version'] <= 1:
                        raise_for.diff_update_bad_version(element)

                    result.append(element)

            elif action == 'delete':
                delete_if_unused: cython.bint = False

                for key, data in elements_data:
                    if key == '@if-unused':  # pyright: ignore[reportUnnecessaryComparison]
                        delete_if_unused = True
                        continue

                    data['@visible'] = False
                    element = _decode_element_unsafe(key, data, changeset_id=changeset_id)

                    if element['version'] <= 1:
                        raise_for.diff_update_bad_version(element)
                    if delete_if_unused:
                        # noinspection PyTypedDict
                        element['delete_if_unused'] = True

                    result.append(element)

            else:
                raise_for.diff_unsupported_action(action)

        return result


@cython.cfunc
def _encode_nodes_json(nodes: list[TypedElementId]) -> list[ElementId]:
    return [type_id[1] for type_id in split_typed_element_ids(nodes)]


@cython.cfunc
def _encode_nodes_xml(nodes: list[TypedElementId]) -> list[dict[str, int]]:
    """
    >>> _encode_nodes_xml([
    ...     ElementMember(type='node', id=1, role=''),
    ...     ElementMember(type='node', id=2, role=''),
    ... ])
    ({'@ref': 1}, {'@ref': 2})
    """
    return [{'@ref': type_id[1]} for type_id in split_typed_element_ids(nodes)]


@cython.cfunc
def _decode_nodes(nodes: list[dict]) -> list[TypedElementId]:
    """
    >>> _decode_nodes([{'@ref': '1'}])
    [ElementMember(type='node', id=1, role='')]
    """
    return [typed_element_id('node', node['@ref']) for node in nodes]


@cython.cfunc
def _encode_members_json(members: list[TypedElementId], members_roles: list[str]) -> list[dict[str, Any]]:
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
    return [
        {'type': type, 'ref': id, 'role': role}
        for (type, id), role in zip(
            split_typed_element_ids(members),
            members_roles,
            strict=True,
        )
    ]


@cython.cfunc
def _encode_members_xml(members: list[TypedElementId], members_roles: list[str]) -> list[dict[str, Any]]:
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
    return [
        {'@type': type, '@ref': id, '@role': role}
        for (type, id), role in zip(
            split_typed_element_ids(members),
            members_roles,
            strict=True,
        )
    ]


# TODO: validate role length
# TODO: validate type
@cython.cfunc
def _decode_members_unsafe(members: list[dict]) -> tuple[list[TypedElementId], list[str]]:
    """
    This method does not validate the input data.

    >>> _decode_members_unsafe([
    ...     {'@type': 'node', '@ref': '1', '@role': 'a'},
    ... ])
    [ElementMember(type='node', id=1, role='a')]
    """
    result: list[TypedElementId] = []
    result_roles: list[str] = []
    for member in members:
        result.append(typed_element_id(member['@type'], member['@ref']))
        result_roles.append(member['@role'])
    return result, result_roles


@cython.cfunc
def _encode_element(element: Element, *, is_json: cython.bint) -> dict:
    """
    >>> _encode_element(Element(type='node', id=1, version=1, ...))
    {'@id': 1, '@version': 1, ...}
    """
    type, id = split_typed_element_id(element['typed_id'])
    is_node: cython.bint = type == 'node'
    is_way: cython.bint = not is_node and type == 'way'
    is_relation: cython.bint = not is_node and not is_way

    tags = element['tags'] or {}
    point = element['point']
    members = element['members']
    members_roles = element['members_roles']

    if is_json:
        return {
            'type': type,
            'id': id,
            'version': element['version'],
            **(
                {
                    'uid': element['user_id'],  # pyright: ignore [reportTypedDictNotRequiredAccess]
                    'user': element['user']['display_name'],
                }
                if 'user' in element
                else {}
            ),
            'changeset': element['changeset_id'],
            'timestamp': legacy_date(element['created_at']),
            'visible': element['visible'],
            'tags': tags,
            **(
                _encode_point_json(point)  #
                if point is not None
                else {}
            ),
            **(
                {'nodes': _encode_nodes_json(members)}  #
                if is_way and members is not None
                else {}
            ),
            **(
                {'members': _encode_members_json(members, members_roles)}
                if is_relation and members is not None and members_roles is not None
                else {}
            ),
        }
    else:
        return {
            '@id': id,
            '@version': element['version'],
            **(
                {
                    '@uid': element['user_id'],  # pyright: ignore [reportTypedDictNotRequiredAccess]
                    '@user': element['user']['display_name'],
                }
                if 'user' in element
                else {}
            ),
            '@changeset': element['changeset_id'],
            '@timestamp': legacy_date(element['created_at']),
            '@visible': element['visible'],
            'tag': [{'@k': k, '@v': v} for k, v in tags.items()],
            **(
                _encode_point_xml(point)  #
                if point is not None
                else {}
            ),
            **(
                {'nd': _encode_nodes_xml(members)}  #
                if is_way and members is not None
                else {}
            ),
            **(
                {'member': _encode_members_xml(members, members_roles)}  #
                if is_relation and members is not None and members_roles is not None
                else {}
            ),
        }


@cython.cfunc
def _decode_element_unsafe(type: ElementType, data: dict, *, changeset_id: ChangesetId | None):
    """
    This method does not validate the input data.

    If changeset_id is None, it will be extracted from the element data.

    >>> decode_element(('node', {'@id': 1, '@version': 1, ...}))
    Element(type='node', ...)
    """
    tags = (
        _decode_tags_unsafe(data_tags)  #
        if (data_tags := data.get('tag')) is not None
        else None
    )
    point = (
        # numpy automatically parses strings
        lib.points(np.array((lon, lat), np.float64).round(GEO_COORDINATE_PRECISION))
        if (lon := data.get('@lon')) is not None  #
        and (lat := data.get('@lat')) is not None
        else None
    )

    # decode members from either nd or member
    if type == 'way' and (data_nodes := data.get('nd')) is not None:
        members = _decode_nodes(data_nodes)
        members_roles = None
    elif type == 'relation' and (data_members := data.get('member')) is not None:
        members, members_roles = _decode_members_unsafe(data_members)
    else:
        members = None
        members_roles = None

    result: ElementInit = {
        'changeset_id': changeset_id if (changeset_id is not None) else data['@changeset'],
        'typed_id': typed_element_id(type, data['@id']),
        'version': data.get('@version', 0) + 1,
        'visible': data.get('@visible', True),
        'tags': tags,
        'point': point,
        'members': members,
        'members_roles': members_roles,
    }
    return result


@cython.cfunc
def _encode_point_json(point: Point) -> dict[str, float]:
    """
    >>> _encode_point_json(Point(1, 2))
    {'lon': 1, 'lat': 2}
    """
    x, y = get_coordinates(point)[0].tolist()
    return {'lon': x, 'lat': y}


@cython.cfunc
def _encode_point_xml(point: Point) -> dict[str, float]:
    """
    >>> _encode_point_xml(Point(1, 2))
    {'@lon': 1, '@lat': 2}
    """
    x, y = get_coordinates(point)[0].tolist()
    return {'@lon': x, '@lat': y}


@cython.cfunc
def _decode_tags_unsafe(tags: list[dict]) -> dict:
    """
    This method does not validate the input data.

    >>> _decode_tags_unsafe([
    ...     {'@k': 'a', '@v': '1'},
    ...     {'@k': 'b', '@v': '2'},
    ... ])
    {'a': '1', 'b': '2'}
    """
    items = [(tag['@k'], tag['@v']) for tag in tags]
    result = dict(items)
    if len(items) != len(result):
        raise ValueError('Duplicate tag keys')
    return result
