from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ValueFormat:
    text: str
    format: Literal['html', 'url', 'url-safe', 'email', 'phone', 'color'] | None = None
    """
    html: HTML code
    url: Unendorsed URL address
    url-safe: Endorsed URL address
    email: Email address
    phone: Phone number
    color: Color code
    None: Plain text
    """
    data: str | None = None


@dataclass(init=False, slots=True)
class TagFormat:
    key: ValueFormat
    values: list[ValueFormat]

    def __init__(self, key: str, value: str):
        self.key = ValueFormat(key)
        self.values = [ValueFormat(v) for v in value.split(';', maxsplit=8)]
