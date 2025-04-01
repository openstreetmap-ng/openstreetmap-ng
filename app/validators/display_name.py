from typing import Annotated

from annotated_types import MaxLen, MinLen

from app.config import DISPLAY_NAME_MAX_LENGTH
from app.models.types import DisplayName
from app.validators.unicode import UnicodeValidator
from app.validators.url import UrlSafeValidator
from app.validators.whitespace import BoundaryWhitespaceValidator
from app.validators.xml import XMLSafeValidator

DisplayNameValidating = Annotated[
    DisplayName,
    UnicodeValidator,
    MinLen(3),
    MaxLen(DISPLAY_NAME_MAX_LENGTH),
    BoundaryWhitespaceValidator,
    UrlSafeValidator,
    XMLSafeValidator,
]
