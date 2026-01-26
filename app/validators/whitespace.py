import string

from pydantic import AfterValidator

from app.lib.translation import t

_WHITESPACE_CHARS = tuple(string.whitespace)


def _validate_boundary_whitespace(v: str):
    if v.startswith(_WHITESPACE_CHARS):
        raise ValueError(t('validations.leading_whitespace'))
    if v.endswith(_WHITESPACE_CHARS):
        raise ValueError(t('validations.trailing_whitespace'))
    return v


BoundaryWhitespaceValidator = AfterValidator(_validate_boundary_whitespace)
