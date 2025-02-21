from typing import Annotated, NewType

from annotated_types import MaxLen, MinLen
from pydantic import SecretStr

from app.limits import DISPLAY_NAME_MAX_LENGTH
from app.validators.url import UrlSafeValidator
from app.validators.whitespace import BoundaryWhitespaceValidator

Str255 = Annotated[str, MinLen(1), MaxLen(255)]
Email = NewType('Email', str)
DisplayName = NewType('DisplayName', str)
DisplayNameValidating = Annotated[
    DisplayName,
    MinLen(3),
    MaxLen(DISPLAY_NAME_MAX_LENGTH),
    UrlSafeValidator,
    BoundaryWhitespaceValidator,
]
LocaleCode = NewType('LocaleCode', str)
Password = NewType('Password', SecretStr)
StorageKey = NewType('StorageKey', str)
Uri = NewType('Uri', str)
