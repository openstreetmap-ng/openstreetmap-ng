from typing import TYPE_CHECKING, Literal, NewType

import cython

if TYPE_CHECKING:
    from app.models.db.element import Element, ElementInit

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


def versioned_typed_element_id(type: ElementType, s: str) -> tuple[TypedElementId, int]:
    """Parse a versioned element reference from a string."""
    idx = s.rindex('v')
    id: ElementId = int(s[:idx])  # type: ignore
    version = int(s[idx + 1 :])
    if id == 0:
        raise ValueError('Element id must be non-zero')
    if version <= 0:
        raise ValueError('Element version must be positive')
    return typed_element_id(type, id), version


def typed_element_id(type: ElementType, id: ElementId) -> TypedElementId:
    """
    Encode element type and id into a 64-bit integer:
    [ 2 reserved bits ][ 2 type bits ][ 1 sign bit ][ 3 reserved bits ][ 56 id bits ]
    """
    result: cython.ulonglong
    type_num: cython.ulonglong

    is_negative: cython.bint = id < 0
    if is_negative:
        if id <= -1 << 56:
            raise OverflowError(f'ElementId {id} is too small for TypedElementId')
        result = -id
        sign_bit: cython.ulonglong = 1 << 59
        result |= sign_bit

    else:
        if id >= 1 << 56:
            raise OverflowError(f'ElementId {id} is too large for TypedElementId')
        result = id

    if type == 'node':
        return result  # type: ignore
    if type == 'way':
        type_num = 1 << 60
        return result | type_num  # type: ignore
    if type == 'relation':
        type_num = 2 << 60
        return result | type_num  # type: ignore

    raise NotImplementedError(f'Unsupported element type {type!r}')


@cython.cfunc
def _split_typed_element_id(id: cython.ulonglong) -> tuple[ElementType, ElementId]:
    sign_bit: cython.ulonglong = 1 << 59
    is_negative: cython.bint = id & sign_bit != 0
    type_num: cython.ulonglong = (id >> 60) & 0b11
    element_id_mask: cython.ulonglong = (1 << 56) - 1
    element_id: int = id & element_id_mask

    if is_negative:
        element_id = -element_id

    if type_num == 0:
        return 'node', element_id  # type: ignore
    if type_num == 1:
        return 'way', element_id  # type: ignore
    if type_num == 2:
        return 'relation', element_id  # type: ignore

    raise NotImplementedError(f'Unsupported element type number {type_num} in {id}')


# TODO: revise usage
def split_typed_element_id(id: TypedElementId) -> tuple[ElementType, ElementId]:
    return _split_typed_element_id(id)


def split_typed_element_ids(
    ids: list[TypedElementId],
) -> list[tuple[ElementType, ElementId]]:
    return [_split_typed_element_id(id) for id in ids]


def split_typed_element_ids2(
    elements: list['Element'] | list['ElementInit'],
) -> list[tuple[ElementType, ElementId]]:
    return [_split_typed_element_id(e['typed_id']) for e in elements]


TYPED_ELEMENT_ID_RELATION_MAX = TypedElementId((3 << 60) - 1)
TYPED_ELEMENT_ID_RELATION_MIN = typed_element_id('relation', ElementId(0))
TYPED_ELEMENT_ID_WAY_MAX = TypedElementId(TYPED_ELEMENT_ID_RELATION_MIN - 1)
TYPED_ELEMENT_ID_WAY_MIN = typed_element_id('way', ElementId(0))
TYPED_ELEMENT_ID_NODE_MAX = TypedElementId(TYPED_ELEMENT_ID_WAY_MIN - 1)
TYPED_ELEMENT_ID_NODE_MIN = typed_element_id('node', ElementId(0))
