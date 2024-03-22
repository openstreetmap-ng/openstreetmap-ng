import logging
from collections.abc import Sequence
from ipaddress import IPv4Address

from app.config import DEFAULT_LANGUAGE, TEST_ENV, TEST_USER_DOMAIN, TEST_USER_PASSWORD
from app.db import db_autocommit
from app.lib.auth_context import auth_context
from app.lib.password_hash import PasswordHash
from app.models.db.user import User
from app.models.str import PasswordStr
from app.models.user_role import UserRole
from app.models.user_status import UserStatus
from app.repositories.user_repository import UserRepository


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
            await TestService.create_user('admin', roles=(UserRole.administrator,))
            await TestService.create_user('moderator', roles=(UserRole.moderator,))
            await TestService.create_user('user1')
            await TestService.create_user('user2')

    if TEST_ENV:

        @staticmethod
        async def create_user(
            name: str,
            *,
            status: UserStatus = UserStatus.active,
            roles: Sequence[UserRole] = (),
        ) -> None:
            """
            Create a test user.
            """

            # skip creation if the user already exists
            if not await UserRepository.check_display_name_available(name):
                logging.debug('Test user %r already exists', name)
                return

            email = f'{name}@{TEST_USER_DOMAIN}'
            password = PasswordStr(TEST_USER_PASSWORD)
            password_hashed = PasswordHash.default().hash(password)

            async with db_autocommit() as session:
                user = User(
                    email=email,
                    display_name=name,
                    password_hashed=password_hashed,
                    created_ip=IPv4Address('127.0.0.1'),
                    status=status,
                    auth_provider=None,
                    auth_uid=None,
                    language=DEFAULT_LANGUAGE,
                    activity_tracking=False,
                    crash_reporting=False,
                )
                user.roles = roles
                session.add(user)

            logging.info('Test user %r created', name)
