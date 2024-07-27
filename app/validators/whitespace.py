import string

import cython
from annotated_types import Predicate

_whitespace_chars = tuple(string.whitespace)


@cython.cfunc
def _validate_boundary_whitespace(s: str) -> bool:
    return not s.startswith(_whitespace_chars) and not s.endswith(_whitespace_chars)


BoundaryWhitespaceValidator = Predicate(_validate_boundary_whitespace)
