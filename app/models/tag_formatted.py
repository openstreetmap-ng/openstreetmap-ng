from typing import NamedTuple

from app.models.tag_format import TagFormat


class TagFormatted(NamedTuple):
    format: TagFormat  # noqa: A003
    value: str
    data: str
