from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class TagFormat:
    value: str
    format: Literal['html', 'url', 'url-safe', 'email', 'phone', 'color'] | None = None
    data: str | None = None


@dataclass(init=False, slots=True)
class TagFormatCollection:
    key: TagFormat
    values: Sequence[TagFormat]

    def __init__(self, key: str, value: str):
        self.key = TagFormat(key)
        self.values = (TagFormat(value),)
