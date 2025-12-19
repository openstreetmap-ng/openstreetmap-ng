from typing import get_args, override

import re2
from starlette.convertors import Convertor

from app.models.element import ElementType


class ElementTypeConvertor(Convertor):
    regex = '|'.join(re2.escape(v) for v in get_args(ElementType))

    @override
    def convert(self, value: str) -> ElementType:
        return value  # type: ignore

    @override
    def to_string(self, value: ElementType) -> str:
        return value
