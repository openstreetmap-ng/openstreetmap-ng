from functools import lru_cache
from typing import TYPE_CHECKING, override

from starlette.convertors import Convertor

if TYPE_CHECKING:
    from app.models.element import ElementType


@lru_cache(maxsize=512)
def element_type(s: str) -> 'ElementType':
    """
    Get the element type from the given string.

    >>> element_type('node')
    'node'
    >>> element_type('w123')
    'way'
    """
    if len(s) == 0:
        raise ValueError('Element type cannot be empty')

    c = s[0]
    if c == 'n':
        return 'node'
    elif c == 'w':
        return 'way'
    elif c == 'r':
        return 'relation'
    else:
        raise ValueError(f'Unknown element type {s!r}')


class ElementTypeConvertor(Convertor):
    regex = r'node|way|relation'
    convert = staticmethod(element_type)

    @override
    def to_string(self, value: 'ElementType') -> str:
        return value
