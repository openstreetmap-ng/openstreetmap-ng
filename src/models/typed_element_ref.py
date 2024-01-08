from dataclasses import dataclass
from typing import Self

from src.models.element_type import ElementType


@dataclass(frozen=True, slots=True)
class TypedElementRef:
    type: ElementType
    typed_id: int

    @property
    def typed_ref(self) -> Self:
        return TypedElementRef(
            type=self.type,
            typed_id=self.typed_id,
        )

    def __str__(self) -> str:
        """
        Produce a string representation of the element reference.

        >>> TypedElementRef(ElementType.node, 123)
        'n123'
        """

        return f'{self.type.value[0]}{self.typed_id}'

    @classmethod
    def from_str(cls, s: str) -> Self:
        """
        Parse an element reference from a string representation.

        >>> TypedElementRef.from_str('n123')
        TypedElementRef(type=<ElementType.node: 'node'>, id=123)
        """

        type, id = s[0], s[1:]
        type = ElementType.from_str(type)
        typed_id = int(id)

        if typed_id == 0:
            raise ValueError('Element id cannot be 0')

        return cls(type, typed_id)
