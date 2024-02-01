from dataclasses import dataclass

from app.models.element_ref import ElementRef
from app.models.str import EmptyStr255


@dataclass(frozen=True, slots=True)
class ElementMemberRef(ElementRef):
    role: EmptyStr255
