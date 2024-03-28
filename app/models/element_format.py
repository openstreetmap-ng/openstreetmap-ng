from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ElementFormat:
    id: int
    version: int
    visible: bool
    icon: str | None
    icon_title: str | None
