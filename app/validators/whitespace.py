import string

from annotated_types import Predicate

_WHITESPACE_CHARS = tuple(string.whitespace)


def _validate_boundary_whitespace(s: str) -> bool:
    return not s.startswith(_WHITESPACE_CHARS) and not s.endswith(_WHITESPACE_CHARS)


BoundaryWhitespaceValidator = Predicate(_validate_boundary_whitespace)
