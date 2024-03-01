from dataclasses import dataclass
from typing import Self

from app.models.element_type import ElementType, element_type


@dataclass(frozen=True, slots=True)
class ElementRef:
    type: ElementType
    id: int

    @property
    def element_ref(self) -> Self:
        return ElementRef(
            type=self.type,
            id=self.id,
        )

    def __str__(self) -> str:
        """
        Produce a string representation of the element reference.

        >>> TypedElementRef(ElementType.node, 123)
        'n123'
        """

        return f'{self.type[0]}{self.id}'

    @classmethod
    def from_str(cls, s: str) -> Self:
        """
        Parse an element reference from a string representation.

        >>> TypedElementRef.from_str('n123')
        TypedElementRef(type=<ElementType.node: 'node'>, id=123)
        """

        type = element_type(s)
        id = int(s[1:])

        if id == 0:
            raise ValueError('Element id cannot be 0')

        return cls(type, id)
