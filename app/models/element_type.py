from typing import Literal

ElementType = Literal['node', 'way', 'relation']


def element_type(s: str) -> ElementType:
    """
    Get the element type from the given string.

    >>> element_type('node')
    'node'
    >>> element_type('w123')
    'way'
    """
    if len(s) == 0:  # TODO: cython check
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
