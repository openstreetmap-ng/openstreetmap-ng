from starlette.convertors import Convertor

from app.models.element_type import ElementType


class ElementTypeConvertor(Convertor):
    regex = r'node|way|relation'

    def convert(self, value: str) -> ElementType:
        return value

    def to_string(self, value: ElementType) -> str:
        return value
