import string

import cython
from annotated_types import Predicate

_whitespace_chars = tuple(string.whitespace)


@cython.cfunc
def _validate_boundary_whitespace(s: str) -> cython.char:
    # read property once for performance
    whitespace_chars = _whitespace_chars
    return not s.startswith(whitespace_chars) and not s.endswith(whitespace_chars)


BoundaryWhitespaceValidator = Predicate(_validate_boundary_whitespace)
