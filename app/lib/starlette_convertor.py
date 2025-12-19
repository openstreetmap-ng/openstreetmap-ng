from typing import get_args, override

import re2
from starlette.convertors import Convertor

from app.models.element import ElementType
from speedup import element_type


class ElementTypeConvertor(Convertor):
    regex = '|'.join(re2.escape(v) for v in get_args(ElementType))
    convert = staticmethod(element_type)  # type: ignore

    @override
    def to_string(self, value: ElementType) -> str:
        return value
