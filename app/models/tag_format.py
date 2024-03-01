from enum import Enum
from typing import NamedTuple


class TagFormat(str, Enum):
    default = 'default'
    color = 'color'
    email = 'email'
    phone = 'phone'
    url = 'url'


class TagFormatted(NamedTuple):
    format: TagFormat  # noqa: A003
    value: str
    data: str
