from collections.abc import Sequence

import cython

from app.format06.element_mixin import Element06Mixin
from app.lib.exceptions_context import raise_for
from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.models.osmchange_action import OSMChangeAction

# read property once for performance
_action_create_value = OSMChangeAction.create.value
_action_modify_value = OSMChangeAction.modify.value
_action_delete_value = OSMChangeAction.delete.value


class OsmChange06Mixin:
    @staticmethod
    def encode_osmchange(elements: Sequence[Element]) -> Sequence[tuple[str, dict]]:
        """
        >>> encode_osmchange([
        ...     Element(type=ElementType.node, id=1, version=1, ...),
        ...     Element(type=ElementType.way, id=2, version=2, ...)
        ... ])
        [
            ('create', {'node': [{'@id': 1, '@version': 1, ...}]}),
            ('modify', {'way': [{'@id': 2, '@version': 2, ...}]}),
        ]
        """

        result = [None] * len(elements)
        i: cython.int

        for i, element in enumerate(elements):
            if element.version == 1:
                action = _action_create_value
            elif element.visible:
                action = _action_modify_value
            else:
                action = _action_delete_value

            result[i] = (action, Element06Mixin.encode_element(element))

        return result

    @staticmethod
    def decode_osmchange(elements: Sequence[tuple[str, dict]], changeset_id: int | None) -> Sequence[Element]:
        """
        If `changeset_id` is `None`, it will be extracted from the element data.

        >>> decode_osmchange([
        ...     ('create', {'node': [{'@id': 1, '@version': 1, ...}]}),
        ...     ('modify', {'way': [{'@id': 2, '@version': 2, ...}]}),
        ... ])
        [Element(type=ElementType, ...), Element(type=ElementType.way, ...)]
        """

        result = [None] * len(elements)
        i: cython.int

        for i, (action, element_dict) in enumerate(elements):
            element_dict_len = len(element_dict)
            if element_dict_len != 1:
                raise ValueError(f'Expected one element in {action!r}, got {element_dict_len}')

            element = Element06Mixin.decode_element(element_dict, changeset_id=changeset_id)

            if action == _action_create_value:
                if element.id > 0:
                    raise_for().diff_create_bad_id(element.versioned_ref)
                element.version = 1

            elif action == _action_modify_value:
                if element.version < 2:
                    raise_for().diff_update_bad_version(element.versioned_ref)

            elif action == _action_delete_value:
                if element.version < 2:
                    raise_for().diff_update_bad_version(element.versioned_ref)
                element.visible = False

            else:
                raise_for().diff_unsupported_action(action)

            result[i] = element

        return result

    @staticmethod
    def encode_diff_result(assigned_ref_map: dict[ElementRef, Sequence[Element]]) -> Sequence[tuple]:
        """
        >>> encode_diff_result({
        ...     TypedElementRef(type=ElementType.node, id=-1): [
        ...         Element(type=ElementType.node, id=1, version=1, ...),
        ...         Element(type=ElementType.node, id=1, version=2, ...),
        ...     ],
        ... })
        [
            ('node', {'@old_id': -1, '@new_id': 1, '@new_version': 1}),
            ('node', {'@old_id': -1, '@new_id': 1, '@new_version': 2})
        ]
        """

        result = []

        for element_ref, elements in assigned_ref_map.items():
            type_str = element_ref.type.value
            old_id = element_ref.id

            for element in elements:
                result.append(  # noqa: PERF401
                    (
                        type_str,
                        {
                            '@old_id': old_id,
                            '@new_id': element.id,
                            '@new_version': element.version,
                        },
                    )
                )

        return result
