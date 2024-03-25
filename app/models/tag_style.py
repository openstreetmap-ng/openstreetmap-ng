from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class TagStyle:
    value: str
    format: Literal['html', 'url', 'url-safe', 'email', 'phone', 'color'] | None = None
    data: str | None = None


@dataclass(init=False, slots=True)
class TagStyleCollection:
    key: TagStyle
    values: Sequence[TagStyle]

    def __init__(self, key: str, value: str):
        self.key = TagStyle(key)
        self.values = (TagStyle(value),)
