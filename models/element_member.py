from typing import NamedTuple

from models.element_type import ElementType


class ElementMember(NamedTuple):
    type: ElementType
    typed_id: int
    role: str
