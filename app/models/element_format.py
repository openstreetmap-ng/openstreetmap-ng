from dataclasses import dataclass

from app.models.element_type import ElementType


@dataclass(frozen=True, slots=True)
class _ElementFormat:
    type: ElementType
    id: int
    name: str | None
    icon: str | None
    icon_title: str | None


@dataclass(frozen=True, slots=True)
class ChangesetElementFormat(_ElementFormat):
    version: int
    visible: bool


@dataclass(frozen=True, slots=True)
class ElementMemberFormat(_ElementFormat):
    role: str | None
