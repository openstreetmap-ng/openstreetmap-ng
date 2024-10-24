from typing import Annotated, NewType

from annotated_types import MaxLen, MinLen
from pydantic import SecretStr

from app.limits import (
    DISPLAY_NAME_MAX_LENGTH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
)
from app.validators.url import UrlSafeValidator
from app.validators.whitespace import BoundaryWhitespaceValidator

Str255 = Annotated[str, MinLen(1), MaxLen(255)]

DisplayNameType = NewType('DisplayNameType', str)
ValidatingDisplayNameType = Annotated[
    DisplayNameType,
    MinLen(3),
    MaxLen(DISPLAY_NAME_MAX_LENGTH),
    UrlSafeValidator,
    BoundaryWhitespaceValidator,
]
EmailType = NewType('EmailType', str)
LocaleCode = NewType('LocaleCode', str)
PasswordType = NewType('PasswordType', SecretStr)
ValidatingPasswordType = Annotated[PasswordType, MinLen(PASSWORD_MIN_LENGTH), MaxLen(PASSWORD_MAX_LENGTH)]
StorageKey = NewType('StorageKey', str)
Uri = NewType('Uri', str)
