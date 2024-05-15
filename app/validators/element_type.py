from starlette.convertors import Convertor

from app.models.element_type import ElementType, element_type


class ElementTypeConvertor(Convertor):
    regex = r'node|way|relation'

    def convert(self, value: str) -> ElementType:
        return element_type(value)

    def to_string(self, value: ElementType) -> str:
        return value
