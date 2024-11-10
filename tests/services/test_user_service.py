from datetime import timedelta

import pytest

from app.lib.auth_context import auth_context
from app.lib.date_utils import utcnow
from app.limits import USER_PENDING_EXPIRE
from app.models.db.user import UserStatus
from app.models.types import DisplayNameType
from app.queries.user_query import UserQuery
from app.services.test_service import TestService
from app.services.user_service import UserService


@pytest.mark.parametrize(
    ('status', 'should_delete'),
    [
        (UserStatus.pending_activation, True),
        (UserStatus.active, False),
    ],
)
async def test_delete_old_pending_users(status: UserStatus, should_delete: bool):
    with auth_context(None, ()):
        display_name = DisplayNameType(f'status_{status.value}')
        created_at = utcnow() - USER_PENDING_EXPIRE - timedelta(days=1)
        await TestService.create_user(display_name, status=status, created_at=created_at)

    await UserService.delete_old_pending_users()
    user = await UserQuery.find_one_by_display_name(display_name)
    assert (user is None) == should_delete
