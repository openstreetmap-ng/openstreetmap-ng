from dataclasses import dataclass
from typing import Self, override

from pydantic import PositiveInt

from app.models.element_ref import ElementRef
from app.models.element_type import ElementType


@dataclass(frozen=True, slots=True)
class VersionedElementRef(ElementRef):
    version: PositiveInt

    def __str__(self) -> str:
        """
        Produce a string representation of the versioned element reference.

        >>> VersionedElementRef(ElementType.node, 123, 1)
        'n123v1'
        """

        return f'{self.type.value[0]}{self.id}v{self.version}'

    @override
    @classmethod
    def from_str(cls, s: str) -> Self:
        """
        Parse a versioned element reference from a string representation.

        >>> VersionedElementRef.from_str('n123v1')
        VersionedElementRef(type=<ElementType.node: 'node'>, id=123, version=1)
        """

        type = ElementType.from_str(s[0])

        i = s.rindex('v')
        id = int(s[1:i])
        version = int(s[i + 1 :])

        if id == 0:
            raise ValueError('Element id cannot be 0')
        if version <= 0:
            raise ValueError('Element version must be positive')

        return cls(type, id, version)

    @classmethod
    def from_type_str(cls, type: ElementType, s: str) -> Self:
        """
        Parse a versioned element reference from a string.

        >>> VersionedElementRef.from_type_str(ElementType.node, '123v1')
        VersionedElementRef(type=<ElementType.node: 'node'>, id=123, version=1)
        """

        idx = s.rindex('v')
        id, version = int(s[:idx]), int(s[idx + 1 :])

        if id == 0:
            raise ValueError('Element id cannot be 0')
        if version <= 0:
            raise ValueError('Element version must be positive')

        return cls(type, id, version)
