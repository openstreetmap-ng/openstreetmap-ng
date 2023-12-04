from typing import Annotated

from annotated_types import MaxLen, MinLen, Predicate
from email_validator.rfc_constants import EMAIL_MAX_LENGTH

from limits import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from validators.str import EmptyEmailStrValidator
from validators.url import URLSafeValidator
from validators.whitespace import BoundaryWhitespaceValidator

EmptyStr255 = Annotated[str, MaxLen(255)]
Str255 = Annotated[EmptyStr255, MinLen(1)]

EmptyEmailStr = Annotated[str, EmptyEmailStrValidator, MaxLen(EMAIL_MAX_LENGTH)]
EmailStr = Annotated[EmptyEmailStr, MinLen(5)]

UserNameStr = Annotated[Str255, MinLen(3), URLSafeValidator, BoundaryWhitespaceValidator]

EmptyPasswordStr = Annotated[str, Predicate(lambda x: not x or PASSWORD_MIN_LENGTH <= len(x) <= PASSWORD_MAX_LENGTH)]
PasswordStr = Annotated[str, MinLen(PASSWORD_MIN_LENGTH), MaxLen(PASSWORD_MAX_LENGTH)]

# TypedElementId = Annotated[
#     NonEmptyStr,
#     TypedElementIdValidator
# ]

# VersionedElementId = Annotated[
#     NonEmptyStr,
#     VersionedElementIdValidator
# ]
