from app.models.db.element import Element, ElementInit
from app.models.element import ElementId, ElementType, TypedElementId

def element_type(s: str, /) -> ElementType:
    """
    Get the element type from the given string.
    >>> element_type('node')
    'node'
    >>> element_type('w123')
    'way'
    """

def typed_element_id(type: ElementType, id: ElementId, /) -> TypedElementId:
    """
    Encode element type and id into a 64-bit integer:
    [ 2 reserved bits ][ 2 type bits ][ 1 sign bit ][ 3 reserved bits ][ 56 id bits ]
    """

def versioned_typed_element_id(
    type: ElementType, s: str, /
) -> tuple[TypedElementId, int]:
    """Parse a versioned element reference from a string."""

def split_typed_element_id(id: TypedElementId, /) -> tuple[ElementType, ElementId]: ...
def split_typed_element_ids(
    ids: list[TypedElementId] | list[Element] | list[ElementInit], /
) -> list[tuple[ElementType, ElementId]]: ...
