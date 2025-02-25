from typing import Annotated, NewType

from annotated_types import Interval, MaxLen, MinLen
from pydantic import SecretStr

from app.limits import DISPLAY_NAME_MAX_LENGTH
from app.validators.unicode import UnicodeValidator
from app.validators.url import UrlSafeValidator
from app.validators.whitespace import BoundaryWhitespaceValidator
from app.validators.xml import XMLSafeValidator

Email = NewType('Email', str)
DisplayName = NewType('DisplayName', str)
DisplayNameValidating = Annotated[
    DisplayName,
    UnicodeValidator,
    MinLen(3),
    MaxLen(DISPLAY_NAME_MAX_LENGTH),
    BoundaryWhitespaceValidator,
    UrlSafeValidator,
    XMLSafeValidator,
]
LocaleCode = NewType('LocaleCode', str)
Password = NewType('Password', SecretStr)
StorageKey = NewType('StorageKey', str)
Uri = NewType('Uri', str)

Longitude = Annotated[float, Interval(ge=-180, le=180)]
Latitude = Annotated[float, Interval(ge=-90, le=90)]
Zoom = Annotated[int, Interval(ge=0, le=25)]
