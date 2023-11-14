from typing import NamedTuple

from models.element_type import ElementType
from models.str import EmptyStr255


class ElementMember(NamedTuple):
    type: ElementType
    typed_id: int
    role: EmptyStr255  # TODO: is this validated?
