from dataclasses import dataclass

from app.models.element_type import ElementType


@dataclass(frozen=True, slots=True)
class ElementFormat:
    type: ElementType
    id: int
    name: str | None
    icon: str | None
    icon_title: str | None

    # changeset render:
    version: int = 0
    visible: bool = True

    # element render:
    role: str | None = None
