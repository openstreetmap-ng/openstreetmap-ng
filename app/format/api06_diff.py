from collections.abc import Iterable

from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.models.element_type import ElementType


class Diff06Mixin:
    @staticmethod
    def encode_diff_result(assigned_ref_map: dict[ElementRef, Iterable[Element]]) -> list[tuple[ElementType, dict]]:
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
        result: list[tuple[ElementType, dict]] = []
        for ref, elements in assigned_ref_map.items():
            ref_type = ref.type
            ref_id = ref.id
            result.extend(
                (
                    ref_type,
                    {
                        '@old_id': ref_id,
                        '@new_id': element.id,
                        '@new_version': element.version,
                    },
                )
                for element in elements
            )
        return result
