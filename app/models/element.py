from functools import lru_cache
from typing import Literal, NamedTuple, NewType, Self, override

ElementId = NewType('ElementId', int)
ElementType = Literal['node', 'way', 'relation']


@lru_cache(maxsize=512)
def element_type(s: str) -> ElementType:
    """
    Get the element type from the given string.

    >>> element_type('node')
    'node'
    >>> element_type('w123')
    'way'
    """
    if len(s) == 0:
        raise ValueError('Element type cannot be empty')

    c = s[0]
    if c == 'n':
        return 'node'
    if c == 'w':
        return 'way'
    if c == 'r':
        return 'relation'
    raise ValueError(f'Unknown element type {s!r}')


class ElementRef(NamedTuple):
    type: ElementType
    id: ElementId

    @classmethod
    def from_str(cls, s: str) -> Self:
        """
        Parse an element reference from a string representation.

        >>> ElementRef.from_str('n123')
        ElementRef(type='node', id=123)
        """
        type = element_type(s)
        id = int(s[1:])
        if id == 0:
            raise ValueError('Element id must be non-zero')
        return cls(type, id)  # type: ignore

    @override
    def __str__(self) -> str:
        """
        Produce a string representation of the element reference.

        >>> ElementRef('node', 123)
        'n123'
        """
        return f'{self.type[0]}{self.id}'


class VersionedElementRef(NamedTuple):
    type: ElementType
    id: ElementId
    version: int

    @classmethod
    def from_str(cls, s: str) -> Self:
        """
        Parse a versioned element reference from a string representation.

        >>> VersionedElementRef.from_str('n123v1')
        VersionedElementRef(type='node', id=123, version=1)
        """
        type = element_type(s)
        idx = s.rindex('v')
        id = int(s[1:idx])
        version = int(s[idx + 1 :])
        if id == 0:
            raise ValueError('Element id must be non-zero')
        if version <= 0:
            raise ValueError('Element version must be positive')
        return cls(type, id, version)  # type: ignore

    @classmethod
    def from_type_str(cls, type: ElementType, s: str) -> Self:
        """
        Parse a versioned element reference from a string.

        >>> VersionedElementRef.from_type_str('node', '123v1')
        VersionedElementRef(type='node', id=123, version=1)
        """
        idx = s.rindex('v')
        id = int(s[:idx])
        version = int(s[idx + 1 :])
        if id == 0:
            raise ValueError('Element id must be non-zero')
        if version <= 0:
            raise ValueError('Element version must be positive')
        return cls(type, id, version)  # type: ignore

    @override
    def __str__(self) -> str:
        """
        Produce a string representation of the versioned element reference.

        >>> VersionedElementRef('node', 123, 1)
        'n123v1'
        """
        return f'{self.type[0]}{self.id}v{self.version}'
