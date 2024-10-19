import logging
from asyncio import TaskGroup
from datetime import datetime
from functools import wraps
from ipaddress import IPv4Address

from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.config import TEST_ENV, TEST_USER_DOMAIN
from app.db import db_commit
from app.lib.auth_context import auth_context
from app.lib.crypto import hash_bytes
from app.lib.locale import DEFAULT_LOCALE
from app.limits import OAUTH_SECRET_PREVIEW_LENGTH
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.user import User, UserRole, UserStatus
from app.models.scope import PUBLIC_SCOPES, Scope
from app.models.types import DisplayNameType, EmailType, LocaleCode, Uri
from app.queries.user_query import UserQuery


def _testmethod(func):
    """
    Decorator to mark a method as runnable only in test environment.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not TEST_ENV:
            raise AssertionError('Test method cannot be called outside test environment')
        return func(*args, **kwargs)

    return wrapper


class TestService:
    @_testmethod
    @staticmethod
    async def on_startup():
        """
        Prepare the test environment.
        """
        with auth_context(None, ()):
            async with TaskGroup() as tg:
                tg.create_task(TestService.create_user(DisplayNameType('admin'), roles=(UserRole.administrator,)))
                tg.create_task(TestService.create_user(DisplayNameType('moderator'), roles=(UserRole.moderator,)))
                tg.create_task(TestService.create_user(DisplayNameType('user1')))
                tg.create_task(TestService.create_user(DisplayNameType('user2')))

            async with TaskGroup() as tg:
                tg.create_task(
                    TestService.create_oauth2_application(
                        name='TestApp',
                        client_id='testapp',
                        client_secret='',
                        scopes=PUBLIC_SCOPES,
                        is_confidential=False,
                    )
                )
                tg.create_task(
                    TestService.create_oauth2_application(
                        name='TestApp-Minimal',
                        client_id='testapp-minimal',
                        client_secret='',
                        scopes=(),
                        is_confidential=False,
                    )
                )
                tg.create_task(
                    TestService.create_oauth2_application(
                        name='TestApp-Secret',
                        client_id='testapp-secret',
                        client_secret='testapp.secret',  # noqa: S106
                        scopes=PUBLIC_SCOPES,
                        is_confidential=True,
                    )
                )

    @_testmethod
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

    @_testmethod
    @staticmethod
    async def create_oauth2_application(
        *,
        name: str,
        client_id: str,
        client_secret: str,
        scopes: tuple[Scope, ...],
        is_confidential: bool,
    ) -> None:
        """
        Create a test OAuth2 application.
        """
        async with db_commit() as session:
            stmt = select(OAuth2Application).where(OAuth2Application.client_id == client_id).with_for_update()
            app = (await session.execute(stmt)).scalar_one_or_none()
            if app is None:
                # create new application
                app = OAuth2Application(
                    user_id=1,
                    name=name,
                    client_id=client_id,
                    scopes=scopes,
                    is_confidential=is_confidential,
                    redirect_uris=(
                        Uri('http://localhost/callback'),
                        Uri('urn:ietf:wg:oauth:2.0:oob'),
                    ),
                )
                app.client_secret_hashed = hash_bytes(client_secret)
                app.client_secret_preview = client_secret[:OAUTH_SECRET_PREVIEW_LENGTH]
                session.add(app)
            else:
                # update existing application
                app.name = name
                app.scopes = scopes
                app.is_confidential = is_confidential

                # TODO: remove after migrations reset
                if app.client_secret_preview is None:
                    app.client_secret_hashed = hash_bytes(client_secret)
                    app.client_secret_preview = client_secret[:OAUTH_SECRET_PREVIEW_LENGTH]

        logging.info('Upserted test OAuth2 application %r', name)
