from typing import Literal, NamedTuple, NewType, Self, override

import cython

ElementType = Literal['node', 'way', 'relation']
ElementId = NewType('ElementId', int)
TypedElementId = NewType('TypedElementId', int)
"""TypedElementId allocates top 4 bits for ElementType, and bottom 60 bits for ElementId."""


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

        >>> ElementRef('node', ElementId(123))
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

        >>> VersionedElementRef('node', ElementId(123), 1)
        'n123v1'
        """
        return f'{self.type[0]}{self.id}v{self.version}'


def typed_element_id(type: ElementType, id: ElementId) -> TypedElementId:
    if id < 0:
        raise ValueError(f"TypedElementId doesn't support negative ids: {id}")
    if id >= 1 << 60:
        raise OverflowError(f'ElementId {id} is too large for TypedElementId')

    if type == 'node':
        return id  # type: ignore
    elif type == 'way':
        return (1 << 60) | id  # type: ignore
    elif type == 'relation':
        return (2 << 60) | id  # type: ignore
    else:
        raise NotImplementedError(f'Unsupported element type {type!r}')


def split_typed_element_id(id: TypedElementId) -> tuple[ElementType, ElementId]:
    element_id: ElementId = id & ((1 << 60) - 1)  # type: ignore
    type_num: cython.ulonglong = id >> 60
    if type_num == 0:
        return 'node', element_id
    elif type_num == 1:
        return 'way', element_id
    elif type_num == 2:
        return 'relation', element_id
    else:
        raise NotImplementedError(f'Unsupported element type number {type_num!r} in {id!r}')


TYPED_ELEMENT_ID_RELATION_MAX = TypedElementId((3 << 60) - 1)
TYPED_ELEMENT_ID_RELATION_MIN = typed_element_id('relation', ElementId(0))
TYPED_ELEMENT_ID_WAY_MAX = TypedElementId(TYPED_ELEMENT_ID_RELATION_MIN - 1)
TYPED_ELEMENT_ID_WAY_MIN = typed_element_id('way', ElementId(0))
TYPED_ELEMENT_ID_NODE_MAX = TypedElementId(TYPED_ELEMENT_ID_WAY_MIN - 1)
TYPED_ELEMENT_ID_NODE_MIN = typed_element_id('node', ElementId(0))
