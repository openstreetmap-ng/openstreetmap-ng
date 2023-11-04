import string

from annotated_types import Predicate

BoundaryWhitespaceValidator = Predicate(lambda s:
                                        not s.startswith(string.whitespace) and
                                        not s.endswith(string.whitespace))
