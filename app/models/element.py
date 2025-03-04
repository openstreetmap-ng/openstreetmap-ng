from collections.abc import Iterable
from typing import Literal, NamedTuple, NewType

import cython

from app.models.db.element import ElementInit

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


# class ElementRef(NamedTuple):
#     type: ElementType
#     id: ElementId
#
#     @classmethod
#     def from_str(cls, s: str) -> Self:
#         """
#         Parse an element reference from a string representation.
#
#         >>> ElementRef.from_str('n123')
#         ElementRef(type='node', id=123)
#         """
#         type = element_type(s)
#         id = int(s[1:])
#         if id == 0:
#             raise ValueError('Element id must be non-zero')
#         return cls(type, id)  # type: ignore
#
#     @override
#     def __str__(self) -> str:
#         """
#         Produce a string representation of the element reference.
#
#         >>> ElementRef('node', ElementId(123))
#         'n123'
#         """
#         return f'{self.type[0]}{self.id}'


class VersionedTypedElementId(NamedTuple):
    typed_id: TypedElementId
    version: int

    # @classmethod
    # def from_str(cls, s: str) -> Self:
    #     """
    #     Parse a versioned element reference from a string representation.
    #
    #     >>> VersionedElementRef.from_str('n123v1')
    #     VersionedElementRef(type='node', id=123, version=1)
    #     """
    #     type = element_type(s)
    #     idx = s.rindex('v')
    #     id = int(s[1:idx])
    #     version = int(s[idx + 1 :])
    #     if id == 0:
    #         raise ValueError('Element id must be non-zero')
    #     if version <= 0:
    #         raise ValueError('Element version must be positive')
    #     return cls(type, id, version)  # type: ignore
    #
    # @classmethod
    # def from_type_str(cls, type: ElementType, s: str) -> Self:
    #     """
    #     Parse a versioned element reference from a string.
    #
    #     >>> VersionedElementRef.from_type_str('node', '123v1')
    #     VersionedElementRef(type='node', id=123, version=1)
    #     """
    #     idx = s.rindex('v')
    #     id = int(s[:idx])
    #     version = int(s[idx + 1 :])
    #     if id == 0:
    #         raise ValueError('Element id must be non-zero')
    #     if version <= 0:
    #         raise ValueError('Element version must be positive')
    #     return cls(type, id, version)  # type: ignore
    #
    # @override
    # def __str__(self) -> str:
    #     """
    #     Produce a string representation of the versioned element reference.
    #
    #     >>> VersionedElementRef('node', ElementId(123), 1)
    #     'n123v1'
    #     """
    #     return f'{self.type[0]}{self.id}v{self.version}'


def typed_element_id(type: ElementType, id: ElementId) -> TypedElementId:
    """
    Encode element type and id into a 64-bit integer:
    [ 1 sign bit ][ 3 type bits ][ 4 reserved bits ][ 56 id bits ]
    """
    result: cython.ulonglong

    is_negative: cython.bint = id < 0
    if is_negative:
        if id <= -1 << 56:
            raise OverflowError(f'ElementId {id} is too small for TypedElementId')
        result = -id
        sign_bit: cython.ulonglong = 1 << 63
        result |= sign_bit

    else:
        if id >= 1 << 56:
            raise OverflowError(f'ElementId {id} is too large for TypedElementId')
        result = id

    if type == 'node':
        return result  # type: ignore
    elif type == 'way':
        type_num: cython.ulonglong = 1 << 60
        return result | type_num  # type: ignore
    elif type == 'relation':
        type_num: cython.ulonglong = 2 << 60
        return result | type_num  # type: ignore

    raise NotImplementedError(f'Unsupported element type {type!r}')


@cython.cfunc
def _split_typed_element_id(id: cython.ulonglong) -> tuple[ElementType, ElementId]:
    sign_bit: cython.ulonglong = 1 << 63
    element_id_mask: cython.ulonglong = (1 << 56) - 1

    is_negative: cython.bint = id & sign_bit != 0
    type_num: cython.ulonglong = (id >> 60) & 0b111
    element_id: cython.longlong = id & element_id_mask

    if is_negative:
        element_id = -element_id

    if type_num == 0:  # noqa: SIM116
        return 'node', element_id  # type: ignore
    elif type_num == 1:
        return 'way', element_id  # type: ignore
    elif type_num == 2:
        return 'relation', element_id  # type: ignore

    raise NotImplementedError(f'Unsupported element type number {type_num!r} in {id!r}')


def split_typed_element_id(id: TypedElementId) -> tuple[ElementType, ElementId]:
    return _split_typed_element_id(id)


def split_typed_element_ids(ids: Iterable[TypedElementId]) -> list[tuple[ElementType, ElementId]]:
    return [_split_typed_element_id(id) for id in ids]


def split_typed_element_ids2(elements: Iterable[ElementInit]) -> list[tuple[ElementType, ElementId]]:
    return [_split_typed_element_id(e['typed_id']) for e in elements]


# Only considering positive ids.
# Negative ids are not stored in the db anyway.
TYPED_ELEMENT_ID_RELATION_MAX = TypedElementId((3 << 60) - 1)
TYPED_ELEMENT_ID_RELATION_MIN = typed_element_id('relation', ElementId(0))
TYPED_ELEMENT_ID_WAY_MAX = TypedElementId(TYPED_ELEMENT_ID_RELATION_MIN - 1)
TYPED_ELEMENT_ID_WAY_MIN = typed_element_id('way', ElementId(0))
TYPED_ELEMENT_ID_NODE_MAX = TypedElementId(TYPED_ELEMENT_ID_WAY_MIN - 1)
TYPED_ELEMENT_ID_NODE_MIN = typed_element_id('node', ElementId(0))
