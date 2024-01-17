from dataclasses import dataclass

from app.models.str import EmptyStr255
from app.models.typed_element_ref import TypedElementRef


@dataclass(frozen=True, slots=True)
class ElementMemberRef(TypedElementRef):
    role: EmptyStr255
