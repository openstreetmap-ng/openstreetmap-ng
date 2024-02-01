from collections import defaultdict
from collections.abc import Sequence

import cython

from app.format06.geometry_mixin import Geometry06Mixin
from app.format06.tag_mixin import Tag06Mixin
from app.lib.auth_context import auth_user
from app.lib.format_style_context import format_is_json
from app.lib.xmltodict import xattr
from app.models.db.element import Element
from app.models.element_member import ElementMemberRef
from app.models.element_type import ElementType
from app.models.validating.element import ElementValidating

# read property once for performance
_type_node = ElementType.node
_type_way = ElementType.way
_type_relation = ElementType.relation


@cython.cfunc
def _encode_nodes(nodes: Sequence[ElementMemberRef]) -> tuple[dict | int, ...]:
    """
    >>> _encode_nodes([
    ...     ElementMemberRef(type=ElementType.node, id=1, role=''),
    ...     ElementMemberRef(type=ElementType.node, id=2, role=''),
    ... ])
    [{'@ref': 1}, {'@ref': 2}]
    """

    if format_is_json():
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

    return tuple(
        ElementMemberRef(
            type=_type_node,
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

    return tuple(
        {
            xattr('type'): member.type.value,
            xattr('ref'): member.id,
            xattr('role'): member.role,
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

    return tuple(
        ElementMemberRef(
            type=ElementType.from_str(member['@type']),
            id=int(member['@ref']),
            role=member['@role'],
        )
        for member in members
    )


class Element06Mixin:
    @staticmethod
    def encode_element(element: Element) -> dict:
        """
        >>> encode_element(Element(type=ElementType.node, id=1, version=1, ...))
        {'node': {'@id': 1, '@version': 1, ...}}
        """

        # read property once for performance
        element_type = element.type

        is_node: cython.char = element_type == _type_node
        is_way: cython.char = not is_node and element_type == _type_way
        is_relation: cython.char = not is_node and not is_way

        if format_is_json():
            return {
                'type': element_type.value,
                'id': element.id,
                **(Geometry06Mixin.encode_point(element.point) if is_node else {}),
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
                **({'nodes': _encode_nodes(element.members)} if is_way else {}),
                **({'members': _encode_members(element.members)} if is_relation else {}),
            }
        else:
            return {
                element_type.value: {
                    '@id': element.id,
                    **(Geometry06Mixin.encode_point(element.point) if is_node else {}),
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
                    'tag': Tag06Mixin.encode_tags(element.tags),
                    **({'nd': _encode_nodes(element.members)} if is_way else {}),
                    **({'member': _encode_members(element.members)} if is_relation else {}),
                }
            }

    @staticmethod
    def decode_element(element: dict, *, changeset_id: int | None) -> Element:
        """
        If `changeset_id` is None, it will be extracted from the element data.
        """

        element_len = len(element)
        if element_len != 1:
            raise ValueError(f'Expected one root element, got {element_len}')

        type, data = next(iter(element.items()))
        type = ElementType.from_str(type)
        data: dict

        if (data_tags := data.get('tag')) is not None:  # noqa: SIM108
            tags = Tag06Mixin.decode_tags_unsafe(data_tags)
        else:
            tags = {}

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
                changeset_id=changeset_id or data.get('@changeset'),
                type=type,
                id=data.get('@id'),
                version=data.get('@version', 0) + 1,
                visible=data.get('@visible', True),
                tags=tags,
                point=Geometry06Mixin.decode_point_unsafe(data),
                members=members,
            ).to_orm_dict()
        )

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
            return {'elements': tuple(Element06Mixin.encode_element(element) for element in elements)}
        else:
            result: dict[str, list[dict]] = defaultdict(list)

            # merge elements of same type together
            for element in elements:
                result[element.type.value].append(Element06Mixin.encode_element(element))

            return result
