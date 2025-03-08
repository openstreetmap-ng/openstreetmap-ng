from typing import TypedDict

from app.models.db.element import ElementInit
from app.models.element import ElementId, ElementType, TypedElementId, split_typed_element_id

Diff06ResultDict = TypedDict(
    'Diff06ResultDict',
    {
        '@old_id': ElementId,
        '@new_id': ElementId,
        '@new_version': int,
    },
)


class Diff06Mixin:
    @staticmethod
    def encode_diff_result(
        assigned_ref_map: dict[TypedElementId, list[ElementInit]],
    ) -> list[tuple[ElementType, Diff06ResultDict]]:
        """
        >>> encode_diff_result({
        ...     ElementRef(type=ElementType.node, id=-1): [
        ...         Element(type=ElementType.node, id=1, version=1, ...),
        ...         Element(type=ElementType.node, id=1, version=2, ...),
        ...     ],
        ... })
        [
            ('node', {'@old_id': -1, '@new_id': 1, '@new_version': 1}),
            ('node', {'@old_id': -1, '@new_id': 1, '@new_version': 2})
        ]
        """
        result: list[tuple[ElementType, Diff06ResultDict]] = []

        for typed_id, elements in assigned_ref_map.items():
            type, old_id = split_typed_element_id(typed_id)
            new_id = split_typed_element_id(elements[0]['typed_id'])[1]
            result.extend(
                (
                    type,
                    {
                        '@old_id': old_id,
                        '@new_id': new_id,
                        '@new_version': element['version'],
                    },
                )
                for element in elements
            )

        return result
