from collections import defaultdict
from collections.abc import Sequence

import cython
import numpy as np
from shapely import Point, get_coordinates, points

from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_json
from app.lib.xmltodict import xattr
from app.models.db.element import Element
from app.models.element_member_ref import ElementMemberRef
from app.models.element_type import ElementType
from app.models.validating.element import ElementValidating


class Element06Mixin:
    @staticmethod
    def encode_element(element: Element) -> dict:
        """
        >>> encode_element(Element(type=ElementType.node, id=1, version=1, ...))
        {'node': {'@id': 1, '@version': 1, ...}}
        """

        if format_is_json():
            return _encode_element(element, is_json=True)
        else:
            return {element.type.value: _encode_element(element, is_json=False)}

    @staticmethod
    def encode_elements(elements: Sequence[Element]) -> dict[str, Sequence[dict]]:
        """
        >>> encode_elements([
        ...     Element(type=ElementType.node, id=1, version=1, ...),
        ...     Element(type=ElementType.way, id=2, version=1,
        ... ])
        {'node': [{'@id': 1, '@version': 1, ...}], 'way': [{'@id': 2, '@version': 1, ...}]}
        """

        if format_is_json():
            return {'elements': tuple(_encode_element(element, is_json=True) for element in elements)}
        else:
            result: dict[str, list[dict]] = defaultdict(list)

            # merge elements of the same type together
            for element in elements:
                type_list: list[dict] = result[element.type.value]
                type_list.append(_encode_element(element, is_json=False))

            return result

    @staticmethod
    def decode_element(element: tuple[str, dict]) -> Element:
        """
        >>> decode_element(('node', {'@id': 1, '@version': 1, ...}))
        Element(type=ElementType.node, ...)
        """

        return _decode_element(element, changeset_id=None)

    @staticmethod
    def encode_osmchange(elements: Sequence[Element]) -> Sequence[tuple[str, dict]]:
        """
        >>> encode_osmchange([
        ...     Element(type=ElementType.node, id=1, version=1, ...),
        ...     Element(type=ElementType.way, id=2, version=2, ...)
        ... ])
        [
            ('create', {'node': {'@id': 1, '@version': 1, ...}}),
            ('modify', {'way': {'@id': 2, '@version': 2, ...}}),
        ]
        """

        result = []

        for element in elements:
            # determine the action automatically
            if element.version == 1:
                action = 'create'
            elif element.visible:
                action = 'modify'
            else:
                action = 'delete'

            result.append((action, {element.type.value: _encode_element(element, is_json=False)}))

        return result

    @staticmethod
    def decode_osmchange(
        changes: Sequence[tuple[str, Sequence[tuple[str, dict]]]], *, changeset_id: int | None
    ) -> Sequence[Element]:
        """
        If `changeset_id` is None, it will be extracted from the element data.

        >>> decode_osmchange([
        ...     ('create', [('node', {'@id': 1, '@version': 1, ...})]),
        ...     ('modify', [('way', {'@id': 2, '@version': 2, ...})])
        ... ])
        [Element(type=ElementType, ...), Element(type=ElementType.way, ...)]
        """

        result = []

        for action, elements_data in changes:
            if action == 'create':
                for element_data in elements_data:
                    element = _decode_element(element_data, changeset_id=changeset_id)
                    element.version = 1

                    if element.id > 0:
                        raise_for().diff_create_bad_id(element.versioned_ref)

                    result.append(element)

            elif action == 'modify':
                for element_data in elements_data:
                    element = _decode_element(element_data, changeset_id=changeset_id)

                    if element.version < 2:
                        raise_for().diff_update_bad_version(element.versioned_ref)

                    result.append(element)

            elif action == 'delete':
                for element_data in elements_data:
                    element = _decode_element(element_data, changeset_id=changeset_id)
                    element.visible = False

                    if element.version < 2:
                        raise_for().diff_update_bad_version(element.versioned_ref)

                    result.append(element)

            else:
                raise_for().diff_unsupported_action(action)

        return result


@cython.cfunc
def _encode_nodes(nodes: Sequence[ElementMemberRef], *, is_json: cython.char) -> tuple[dict | int, ...]:
    """
    >>> _encode_nodes([
    ...     ElementMemberRef(type=ElementType.node, id=1, role=''),
    ...     ElementMemberRef(type=ElementType.node, id=2, role=''),
    ... ])
    [{'@ref': 1}, {'@ref': 2}]
    """

    if is_json:
        return tuple(node.id for node in nodes)
    else:
        return tuple({'@ref': node.id} for node in nodes)


@cython.cfunc
def _decode_nodes_unsafe(nodes: Sequence[dict]) -> tuple[ElementMemberRef, ...]:
    """
    This method does not validate the input data.

    >>> _decode_nodes_unsafe([{'@ref': '1'}])
    [ElementMemberRef(type=ElementType.node, id=1, role='')]
    """

    # read property once for performance
    type_node = ElementType.node

    return tuple(
        ElementMemberRef(
            type=type_node,
            id=int(node['@ref']),
            role='',
        )
        for node in nodes
    )


@cython.cfunc
def _encode_members(members: Sequence[ElementMemberRef]) -> tuple[dict, ...]:
    """
    >>> _encode_members([
    ...     ElementMemberRef(type=ElementType.node, id=1, role='a'),
    ...     ElementMemberRef(type=ElementType.way, id=2, role='b'),
    ... ])
    [
        {'@type': 'node', '@ref': 1, '@role': 'a'},
        {'@type': 'way', '@ref': 2, '@role': 'b'},
    ]
    """

    xattr_ = xattr  # read property once for performance

    return tuple(
        {
            xattr_('type'): member.type.value,
            xattr_('ref'): member.id,
            xattr_('role'): member.role,
        }
        for member in members
    )


@cython.cfunc
def _decode_members_unsafe(members: Sequence[dict]) -> tuple[ElementMemberRef, ...]:
    """
    This method does not validate the input data.

    >>> _decode_members_unsafe([
    ...     {'@type': 'node', '@ref': '1', '@role': 'a'},
    ... ])
    [ElementMemberRef(type=ElementType.node, id=1, role='a')]
    """

    # read property once for performance
    type_from_str = ElementType.from_str

    return tuple(
        ElementMemberRef(
            type=type_from_str(member['@type']),
            id=int(member['@ref']),
            role=member['@role'],
        )
        for member in members
    )


@cython.cfunc
def _encode_element(element: Element, *, is_json: cython.char) -> dict:
    """
    >>> _encode_element(Element(type=ElementType.node, id=1, version=1, ...))
    {'@id': 1, '@version': 1, ...}
    """

    # read property once for performance
    element_type_str = element.type.value

    is_node: cython.char = element_type_str == 'node'
    is_way: cython.char = not is_node and element_type_str == 'way'
    is_relation: cython.char = not is_node and not is_way

    if is_json:
        return {
            'type': element_type_str,
            'id': element.id,
            **(_encode_point(element.point) if is_node else {}),
            'version': element.version,
            'timestamp': element.created_at,
            'changeset': element.changeset_id,
            **(
                {
                    'uid': element.user_id,
                    'user': element.user.display_name,
                }
                if element.user_id is not None
                else {}
            ),
            'visible': element.visible,
            'tags': element.tags,
            **({'nodes': _encode_nodes(element.members, is_json=True)} if is_way else {}),
            **({'members': _encode_members(element.members)} if is_relation else {}),
        }
    else:
        return {
            '@id': element.id,
            **(_encode_point(element.point) if is_node else {}),
            '@version': element.version,
            '@timestamp': element.created_at,
            '@changeset': element.changeset_id,
            **(
                {
                    '@uid': element.user_id,
                    '@user': element.user.display_name,
                }
                if element.user_id is not None
                else {}
            ),
            '@visible': element.visible,
            'tag': tuple({'@k': k, '@v': v} for k, v in element.tags.items()),
            **({'nd': _encode_nodes(element.members, is_json=False)} if is_way else {}),
            **({'member': _encode_members(element.members)} if is_relation else {}),
        }


@cython.cfunc
def _decode_element(element: tuple[str, dict], *, changeset_id: int | None):
    """
    If `changeset_id` is None, it will be extracted from the element data.

    >>> decode_element(('node', {'@id': 1, '@version': 1, ...}))
    Element(type=ElementType.node, ...)
    """

    type = ElementType.from_str(element[0])
    data: dict = element[1]

    if (data_tags := data.get('tag')) is not None:  # noqa: SIM108
        tags = _decode_tags_unsafe(data_tags)
    else:
        tags = {}

    if (lon := data.get('@lon')) is None or (lat := data.get('@lat')) is None:
        point = None
    else:
        # numpy automatically parses strings
        point = points(np.array((lon, lat), np.float64))

    # decode members from either nd or member
    if (data_nodes := data.get('nd')) is not None:
        members = _decode_nodes_unsafe(data_nodes)
    elif (data_members := data.get('member')) is not None:
        members = _decode_members_unsafe(data_members)
    else:
        members = ()

    return Element(
        **ElementValidating(
            user_id=auth_user().id,
            changeset_id=changeset_id if (changeset_id is not None) else data.get('@changeset'),
            type=type,
            id=data.get('@id'),
            version=data.get('@version', 0) + 1,
            visible=data.get('@visible', True),
            tags=tags,
            point=point,
            members=members,
        ).to_orm_dict()
    )


@cython.cfunc
def _encode_point(point: Point) -> dict:
    """
    >>> _encode_point(Point(1, 2))
    {'@lon': 1, '@lat': 2}
    """

    xattr_ = xattr  # read property once for performance
    x, y = get_coordinates(point)[0].tolist()

    return {
        xattr_('lon'): x,
        xattr_('lat'): y,
    }


@cython.cfunc
def _decode_tags_unsafe(tags: Sequence[dict]) -> dict:
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
        raise ValueError('Duplicate tags keys')

    return result
