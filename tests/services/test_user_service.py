from datetime import datetime, timedelta

from sqlalchemy import select

from app.db import db
from app.lib.auth_context import auth_context
from app.lib.date_utils import legacy_date
from app.lib.options_context import apply_options_context
from app.limits import USER_PENDING_EXPIRE
from app.models.db.user import User
from app.models.user_status import UserStatus
from app.services.test_service import TestService
from app.services.user_service import UserService


async def test_delete_old_pending_users():
    users_created = {
        'old_pending_activation': UserStatus.pending_activation,
        'old_pending_terms': UserStatus.pending_terms,
        'old_active': UserStatus.active,
        'new_pending_activation': UserStatus.pending_activation,
        'new_pending_terms': UserStatus.pending_terms,
        'new_active': UserStatus.active,
    }
    with auth_context(None, ()):
        new_date = legacy_date(datetime.now())
        time_delta = timedelta(days=400)
        assert time_delta > USER_PENDING_EXPIRE
        old_date = new_date - time_delta
        for display_name, status in users_created.items():
            created_at = old_date if display_name.startswith('old') else new_date
            await TestService.create_user(display_name, status=status, created_at=created_at)

    async def get_users():
        async with db() as session:
            stmt = select(User).where(User.display_name.in_(users_created))
            stmt = apply_options_context(stmt)
            return (await session.scalars(stmt)).all()

    all_user_names = set(users_created.keys())
    assert set(map(lambda u: u.display_name, await get_users())) == all_user_names

    await UserService.delete_old_pending_users()

    expected_user_names_left = all_user_names - {'old_pending_activation', 'old_pending_terms'}
    assert set(map(lambda u: u.display_name, await get_users())) == expected_user_names_left
