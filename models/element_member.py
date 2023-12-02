from dataclasses import dataclass

from models.str import EmptyStr255
from models.typed_element_ref import TypedElementRef


@dataclass(frozen=True, slots=True)
class ElementMemberRef(TypedElementRef):
    role: EmptyStr255
