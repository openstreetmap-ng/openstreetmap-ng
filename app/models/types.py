from typing import Annotated, Literal, NewType

from annotated_types import MaxLen, MinLen
from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from pydantic import SecretStr

from app.limits import (
    DISPLAY_NAME_MAX_LENGTH,
    EMAIL_MIN_LENGTH,
    OAUTH_APP_URI_MAX_LENGTH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
)
from app.validators.email import EmailValidator
from app.validators.url import UriValidator, UrlSafeValidator
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
ValidatingEmailType = Annotated[EmailType, EmailValidator, MinLen(EMAIL_MIN_LENGTH), MaxLen(EMAIL_MAX_LENGTH)]
LocaleCode = NewType('LocaleCode', str)
OSMChangeAction = Literal['create', 'modify', 'delete']
PasswordType = NewType('PasswordType', SecretStr)
ValidatingPasswordType = Annotated[PasswordType, MinLen(PASSWORD_MIN_LENGTH), MaxLen(PASSWORD_MAX_LENGTH)]
StorageKey = NewType('StorageKey', str)
Uri = NewType('Uri', str)
ValidatingUri = Annotated[Uri, UriValidator, MinLen(3), MaxLen(OAUTH_APP_URI_MAX_LENGTH)]
