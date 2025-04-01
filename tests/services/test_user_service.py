from datetime import timedelta

import pytest

from app.config import USER_PENDING_EXPIRE
from app.lib.date_utils import utcnow
from app.models.types import DisplayName
from app.queries.user_query import UserQuery
from app.services.test_service import TestService
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
    display_name = DisplayName(f'email_{"verified" if email_verified else "unverified"}')
    created_at = utcnow() - USER_PENDING_EXPIRE - timedelta(days=1)
    await TestService.create_user(display_name, email_verified=email_verified, created_at=created_at)

    # Delete old pending users
    await UserService.delete_old_pending_users()

    # Check if the user still exists after the service call
    user = await UserQuery.find_one_by_display_name(display_name)

    # Assert the expected outcome based on email verification status
    assert (user is None) == should_delete, (
        f'User with {email_verified=} must be {"deleted" if should_delete else "kept"}'
    )
