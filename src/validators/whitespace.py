import string

from annotated_types import Predicate

_WHITESPACE = tuple(string.whitespace)

BoundaryWhitespaceValidator = Predicate(lambda s: not s.startswith(_WHITESPACE) and not s.endswith(_WHITESPACE))
