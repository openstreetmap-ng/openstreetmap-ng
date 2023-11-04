from functools import cache
from typing import Annotated, Self

from pydantic import BaseModel, Field

from models.element_type import ElementType
from validators.eq import Ne


class TypedElementRef(BaseModel):
    type: Annotated[ElementType, Field(frozen=True)]
    id: Annotated[int, Ne(0), Field(frozen=True)]

    @cache
    def __hash__(self) -> int:
        return hash((self.type, self.id))

    @cache
    def __str__(self) -> str:
        '''
        Produce a string representation of the element reference.

        >>> TypedElementRef(ElementType.node, 123)
        'n123'
        '''

        return f'{self.type.value[0]}{self.id}'

    @classmethod
    def from_str(cls, s: str) -> Self:
        '''
        Parse an element reference from a string.

        >>> TypedElementRef.from_str('n123')
        TypedElementRef(type=<ElementType.node: 'node'>, id=123)
        '''

        type, id = s[0], s[1:]
        return cls(
            type=ElementType.from_str(type),
            id=int(id))
