from typing import Literal, NewType

from speedup import typed_element_id

ElementType = Literal['node', 'way', 'relation']
ElementId = NewType('ElementId', int)
TypedElementId = NewType('TypedElementId', int)
"""TypedElementId allocates top 4 bits for ElementType, and bottom 60 bits for ElementId."""

TYPED_ELEMENT_ID_RELATION_MAX = TypedElementId((3 << 60) - 1)
TYPED_ELEMENT_ID_RELATION_MIN = typed_element_id('relation', ElementId(0))
TYPED_ELEMENT_ID_WAY_MAX = TypedElementId(TYPED_ELEMENT_ID_RELATION_MIN - 1)
TYPED_ELEMENT_ID_WAY_MIN = typed_element_id('way', ElementId(0))
TYPED_ELEMENT_ID_NODE_MAX = TypedElementId(TYPED_ELEMENT_ID_WAY_MIN - 1)
TYPED_ELEMENT_ID_NODE_MIN = typed_element_id('node', ElementId(0))
