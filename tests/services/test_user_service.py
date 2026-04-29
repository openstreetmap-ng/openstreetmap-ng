from datetime import timedelta

import pytest
from pydantic import SecretStr

from app.config import USER_PENDING_EXPIRE
from app.lib.auth_context import auth_context
from app.lib.date_utils import utcnow
from app.lib.locale import DEFAULT_LOCALE
from app.lib.translation import translation_context
from app.models.types import DisplayName
from app.queries.user_query import UserQuery
from app.services.test_service import TestService
from app.services.user_recovery_code_service import UserRecoveryCodeService
from app.services.user_service import UserService


@pytest.mark.parametrize(
    ('email_verified', 'should_delete'),
    [
        (False, True),  # unverified (pending) user should be deleted
        (True, False),  # verified (active) user should not be deleted
    ],
)
async def test_delete_old_pending_users(email_verified: bool, should_delete: bool):
    # Create a user that's older than the expiration period
    display_name = DisplayName(
        f'email_{"verified" if email_verified else "unverified"}'
    )
    created_at = utcnow() - USER_PENDING_EXPIRE - timedelta(days=1)
    await TestService.create_user(
        display_name,
        email_verified=email_verified,
        created_at=created_at,
    )

    # Delete old pending users
    await UserService.delete_old_pending_users()

    # Check if the user still exists after the service call
    user = await UserQuery.find_by_display_name(display_name)

    # Assert the expected outcome based on email verification status
    assert (user is None) == should_delete, (
        f'User with {email_verified=} must be {"deleted" if should_delete else "kept"}'
    )


async def test_login_with_recovery_codes_only_does_not_require_2fa():
    # Arrange - create a user with recovery codes
    display_name = DisplayName('user-recovery-only')
    await TestService.create_user(display_name)

    user = await UserQuery.find_by_display_name(display_name)
    assert user is not None

    with translation_context(DEFAULT_LOCALE), auth_context(user):
        await UserRecoveryCodeService.generate_recovery_codes(password=b'anything')

    # Act - attempt to login
    result = await UserService.login(
        display_name_or_email=display_name,
        password=b'anything',
        passkey=None,
        totp_code=None,
        recovery_code=None,
    )

    # Assert - login should succeed without requiring 2FA
    assert isinstance(result, SecretStr)
