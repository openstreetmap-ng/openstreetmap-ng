from dataclasses import dataclass

from app.models.element_type import ElementType


@dataclass(frozen=True, slots=True)
class _BaseListEntry:
    type: ElementType
    id: int
    name: str | None
    icon: str | None
    icon_title: str | None


@dataclass(frozen=True, slots=True)
class ChangesetElementEntry(_BaseListEntry):
    version: int
    visible: bool


@dataclass(frozen=True, slots=True)
class ElementMemberEntry(_BaseListEntry):
    role: str | None
