from collections import defaultdict
from collections.abc import Sequence

import cython

from app.format06.geometry_mixin import Geometry06Mixin
from app.format06.tags_mixin import Tags06Mixin
from app.lib.auth_context import auth_user
from app.lib.format_style_context import format_is_json
from app.lib.xmltodict import XAttr
from app.models.db.element import Element
from app.models.element_member import ElementMemberRef
from app.models.element_type import ElementType
from app.models.validating.element import ElementValidating


@cython.cfunc
def _encode_nodes(nodes: Sequence[ElementMemberRef]) -> tuple[dict | int, ...]:
    """
    >>> _encode_nodes([
    ...     ElementMember(type=ElementType.node, typed_id=1, role=''),
    ...     ElementMember(type=ElementType.node, typed_id=2, role=''),
    ... ])
    [{'@ref': 1}, {'@ref': 2}]
    """

    if format_is_json():
        return tuple(node.typed_id for node in nodes)
    else:
        return tuple({'@ref': node.typed_id} for node in nodes)


@cython.cfunc
def _decode_nodes_unsafe(nodes: Sequence[dict]) -> tuple[ElementMemberRef, ...]:
    """
    This method does not validate the input data.

    >>> _decode_nodes_unsafe([{'@ref': '1'}])
    [ElementMember(type=ElementType.node, typed_id=1, role='')]
    """

    return tuple(
        ElementMemberRef(
            type=ElementType.node,
            typed_id=int(node['@ref']),
            role='',
        )
        for node in nodes
    )


@cython.cfunc
def _encode_members(members: Sequence[ElementMemberRef]) -> tuple[dict, ...]:
    """
    >>> _encode_members([
    ...     ElementMember(type=ElementType.node, typed_id=1, role='a'),
    ...     ElementMember(type=ElementType.way, typed_id=2, role='b'),
    ... ])
    [
        {'@type': 'node', '@ref': 1, '@role': 'a'},
        {'@type': 'way', '@ref': 2, '@role': 'b'},
    ]
    """

    return tuple(
        {
            XAttr('type'): member.type.value,
            XAttr('ref'): member.typed_id,
            XAttr('role'): member.role,
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
    [ElementMember(type=ElementType.node, typed_id=1, role='a')]
    """

    return tuple(
        ElementMemberRef(
            type=ElementType.from_str(member['@type']),
            typed_id=int(member['@ref']),
            role=member['@role'],
        )
        for member in members
    )


class Element06Mixin:
    @staticmethod
    def encode_element(element: Element) -> dict:
        """
        >>> encode_element(Element(type=ElementType.node, typed_id=1, version=1, ...))
        {'node': {'@id': 1, '@version': 1, ...}}
        """

        # read property once for performance
        element_type = element.type

        if format_is_json():
            return {
                'type': element_type.value,
                'id': element.typed_id,
                **(Geometry06Mixin.encode_point(element.point) if element_type == ElementType.node else {}),
                'version': element.version,
                'timestamp': element.created_at,
                'changeset': element.changeset_id,
                'uid': element.user_id,
                'user': element.user.display_name,
                'visible': element.visible,
                'tags': element.tags,
                **({'nodes': _encode_nodes(element.members)} if element_type == ElementType.way else {}),
                **({'members': _encode_members(element.members)} if element_type == ElementType.relation else {}),
            }
        else:
            return {
                element_type.value: {
                    '@id': element.typed_id,
                    **(Geometry06Mixin.encode_point(element.point) if element_type == ElementType.node else {}),
                    '@version': element.version,
                    '@timestamp': element.created_at,
                    '@changeset': element.changeset_id,
                    '@uid': element.user_id,
                    '@user': element.user.display_name,
                    '@visible': element.visible,
                    'tag': Tags06Mixin.encode_tags(element.tags),
                    **({'nd': _encode_nodes(element.members)} if element_type == ElementType.way else {}),
                    **({'member': _encode_members(element.members)} if element_type == ElementType.relation else {}),
                }
            }

    @staticmethod
    def decode_element(element: dict, changeset_id: int | None) -> Element:
        """
        If `changeset_id` is `None`, it will be extracted from the element data.
        """

        if len(element) != 1:
            raise ValueError(f'Expected one root element, got {len(element)}')

        type, data = next(iter(element.items()))
        type = ElementType.from_str(type)
        data: dict

        # decode members from either nd or member
        if data_nodes := data.get('nd'):
            members = _decode_nodes_unsafe(data_nodes)
        elif data_members := data.get('member'):
            members = _decode_members_unsafe(data_members)
        else:
            members = ()

        return Element(
            **ElementValidating(
                user_id=auth_user().id,
                changeset_id=changeset_id or data.get('@changeset'),
                type=type,
                typed_id=data.get('@id'),
                version=data.get('@version', 0) + 1,
                visible=data.get('@visible', True),
                tags=Tags06Mixin.decode_tags_unsafe(data.get('tag', ())),
                point=Geometry06Mixin.decode_point_unsafe(data),
                members=members,
            ).to_orm_dict()
        )

    @staticmethod
    def encode_elements(elements: Sequence[Element]) -> dict[str, Sequence[dict]]:
        """
        >>> encode_elements([
        ...     Element(type=ElementType.node, typed_id=1, version=1, ...),
        ...     Element(type=ElementType.way, typed_id=2, version=1,
        ... ])
        {'node': [{'@id': 1, '@version': 1, ...}], 'way': [{'@id': 2, '@version': 1, ...}]}
        """

        if format_is_json():
            return {'elements': tuple(Element06Mixin.encode_element(element) for element in elements)}
        else:
            result: dict[str, list[dict]] = defaultdict(list)

            for element in elements:
                result[element.type.value].append(Element06Mixin.encode_element(element))

            return result
