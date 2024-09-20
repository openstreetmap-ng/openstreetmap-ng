import logging
from asyncio import TaskGroup
from datetime import datetime
from ipaddress import IPv4Address

from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.config import TEST_ENV, TEST_USER_DOMAIN
from app.db import db_commit
from app.lib.auth_context import auth_context
from app.lib.locale import DEFAULT_LOCALE
from app.models.db.user import User, UserRole, UserStatus
from app.models.types import DisplayNameType, EmailType, LocaleCode
from app.queries.user_query import UserQuery


class TestService:
    @staticmethod
    async def on_startup():
        """
        Prepare the test environment.

        Does nothing if not in test environment.
        """
        if not TEST_ENV:
            return

        with auth_context(None, ()):
            async with TaskGroup() as tg:
                tg.create_task(TestService.create_user(DisplayNameType('admin'), roles=(UserRole.administrator,)))
                tg.create_task(TestService.create_user(DisplayNameType('moderator'), roles=(UserRole.moderator,)))
                tg.create_task(TestService.create_user(DisplayNameType('user1')))
                tg.create_task(TestService.create_user(DisplayNameType('user2')))

    # Additional safeguard against running this in production
    if TEST_ENV:

        @staticmethod
        async def create_user(
            name: DisplayNameType,
            *,
            status: UserStatus = UserStatus.active,
            language: LocaleCode = DEFAULT_LOCALE,
            created_at: datetime | None = None,
            roles: tuple[UserRole, ...] = (),
        ) -> None:
            """
            Create a test user.
            """
            email = EmailType(f'{name}@{TEST_USER_DOMAIN}')
            name_available = await UserQuery.check_display_name_available(name)

            async with db_commit() as session:
                if name_available:
                    # create new user
                    user = User(
                        email=email,
                        display_name=name,
                        password_hashed='',
                        created_ip=IPv4Address('127.0.0.1'),
                        status=status,
                        auth_provider=None,
                        auth_uid=None,
                        language=language,
                        activity_tracking=False,
                        crash_reporting=False,
                    )
                    if created_at is not None:
                        user.created_at = created_at
                    user.roles = roles
                    session.add(user)
                else:
                    # update existing user (happens after preloading real users)
                    stmt = select(User).options(load_only(User.id)).where(User.display_name == name).with_for_update()
                    user = (await session.execute(stmt)).scalar_one()
                    user.email = email
                    user.password_hashed = ''
                    user.status = status
                    user.language = language
                    if created_at is not None:
                        user.created_at = created_at
                    user.roles = roles

                if not user.is_test_user:
                    raise AssertionError('Test service must only create test users')

            logging.info('Upserted test user %r', name)
