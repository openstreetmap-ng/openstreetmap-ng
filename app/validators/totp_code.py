from typing import Annotated

from pydantic import BeforeValidator


def validate_totp_code(value: str) -> str:
    """
    Validate TOTP code format.

    Accepts: 6-digit numeric string (000000-999999)
    Raises: ValueError if invalid format
    """
    if not isinstance(value, str):
        raise ValueError('TOTP code must be a string')

    if len(value) != 6:
        raise ValueError('TOTP code must be exactly 6 digits')

    if not value.isdigit():
        raise ValueError('TOTP code must contain only digits')

    return value


TOTPCodeValidator = BeforeValidator(validate_totp_code)

TOTPCodeValidating = Annotated[
    str,
    TOTPCodeValidator,
]
