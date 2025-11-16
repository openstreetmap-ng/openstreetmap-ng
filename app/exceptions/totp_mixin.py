"""TOTP (Two-Factor Authentication) exceptions mixin."""

from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError


class TOTPExceptionsMixin:
    """TOTP-related exceptions."""

    def totp_invalid_code(self) -> NoReturn:
        """Raise when TOTP code is invalid."""
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Invalid or expired authentication code',
        )

    def totp_already_enabled(self) -> NoReturn:
        """Raise when user tries to enable 2FA but it's already enabled."""
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Two-factor authentication is already enabled',
        )

    def totp_not_enabled(self) -> NoReturn:
        """Raise when user tries to remove 2FA but it's not enabled."""
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Two-factor authentication is not enabled',
        )

    def totp_required(self) -> NoReturn:
        """Raise when 2FA code is required but not provided."""
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail='Two-factor authentication code required',
        )
