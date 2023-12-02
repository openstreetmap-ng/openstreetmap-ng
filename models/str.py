from typing import Annotated

from annotated_types import MaxLen, MinLen
from pydantic import Strict

from validators.str import HexStrValidator
from validators.url import URLSafeValidator
from validators.whitespace import BoundaryWhitespaceValidator

NonEmptyStr = Annotated[str, Strict(), MinLen(1)]  # TODO: dont' use
Str255 = Annotated[str, Strict(), MinLen(1), MaxLen(255)]
EmptyStr255 = Annotated[str, Strict(), MaxLen(255)]
HexStr = Annotated[NonEmptyStr, HexStrValidator]

# TODO: test case
EmailStr = Annotated[
    NonEmptyStr, MaxLen(998)
    # no automatic email validation, use: python-email-validator
]

UserNameStr = Annotated[Str255, MinLen(3), URLSafeValidator, BoundaryWhitespaceValidator]
PasswordStr = Annotated[Str255, MinLen(8)]

# TypedElementId = Annotated[
#     NonEmptyStr,
#     TypedElementIdValidator
# ]

# VersionedElementId = Annotated[
#     NonEmptyStr,
#     VersionedElementIdValidator
# ]
