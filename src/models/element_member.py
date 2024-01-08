from dataclasses import dataclass

from src.models.str import EmptyStr255
from src.models.typed_element_ref import TypedElementRef


@dataclass(frozen=True, slots=True)
class ElementMemberRef(TypedElementRef):
    role: EmptyStr255
