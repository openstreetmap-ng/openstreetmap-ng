from typing import Annotated

from annotated_types import MaxLen, MinLen
from email_validator.rfc_constants import EMAIL_MAX_LENGTH

from app.limits import DISPLAY_NAME_MAX_LENGTH, PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.validators.str import EmailStrValidator
from app.validators.url import URLSafeValidator
from app.validators.whitespace import BoundaryWhitespaceValidator

EmptyStr255 = Annotated[str, MaxLen(255)]
Str255 = Annotated[str, MinLen(1), MaxLen(255)]

# EmptyEmailStr = Annotated[str, EmptyEmailStrValidator, MaxLen(EMAIL_MAX_LENGTH)]
EmailStr = Annotated[str, EmailStrValidator, MinLen(5), MaxLen(EMAIL_MAX_LENGTH)]

UserNameStr = Annotated[str, MinLen(3), MaxLen(DISPLAY_NAME_MAX_LENGTH), URLSafeValidator, BoundaryWhitespaceValidator]

# EmptyPasswordStr = Annotated[str, Predicate(lambda x: not x or PASSWORD_MIN_LENGTH <= len(x) <= PASSWORD_MAX_LENGTH)]
PasswordStr = Annotated[str, MinLen(PASSWORD_MIN_LENGTH), MaxLen(PASSWORD_MAX_LENGTH)]

# TypedElementId = Annotated[
#     NonEmptyStr,
#     TypedElementIdValidator
# ]

# VersionedElementId = Annotated[
#     NonEmptyStr,
#     VersionedElementIdValidator
# ]
