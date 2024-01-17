import string

from annotated_types import Predicate

_whitespace_chars = tuple(string.whitespace)

BoundaryWhitespaceValidator = Predicate(
    lambda s: not s.startswith(_whitespace_chars) and not s.endswith(_whitespace_chars)
)
