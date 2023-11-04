from functools import cache
from typing import Annotated, Self

from pydantic import Field, PositiveInt

from models.element_type import ElementType
from models.typed_element_ref import TypedElementRef


class VersionedElementRef(TypedElementRef):
    version: Annotated[PositiveInt, Field(frozen=True)]

    @cache
    def __hash__(self) -> int:
        return hash((self.type, self.id, self.version))

    @cache
    def __str__(self) -> str:
        '''
        Produce a string representation of the versioned element reference.

        >>> VersionedElementRef(ElementType.node, 123, 1)
        'n123v1'
        '''

        return f'{self.type.value[0]}{self.id}v{self.version}'

    @classmethod
    def from_str(cls, s: str) -> Self:
        '''
        Parse a versioned element reference from a string.

        >>> VersionedElementRef.from_str('n123v1')
        VersionedElementRef(type=<ElementType.node: 'node'>, id=123, version=1)
        '''

        i = s.rindex('v')
        type, id, version = s[0], s[1:i], s[i + 1:]
        return cls(
            type=ElementType.from_str(type),
            id=int(id),
            version=int(version))

    @classmethod
    def from_typed_str(cls, type: ElementType, s: str) -> Self:
        '''
        Parse a versioned element reference from a string.

        >>> VersionedElementRef.from_typed_str(ElementType.node, '123v1')
        VersionedElementRef(type=<ElementType.node: 'node'>, id=123, version=1)
        '''

        i = s.rindex('v')
        id, version = s[:i], s[i + 1:]
        return cls(
            type=type,
            id=int(id),
            version=int(version))
