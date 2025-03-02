from typing import override

from starlette.convertors import Convertor

from app.models.element import ElementType, element_type


class ElementTypeConvertor(Convertor):
    regex = r'node|way|relation'
    convert = staticmethod(element_type)  # type: ignore

    @override
    def to_string(self, value: ElementType) -> str:
        return value
