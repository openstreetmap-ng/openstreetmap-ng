import logging
from asyncio import TaskGroup
from datetime import datetime

from psycopg.errors import UniqueViolation
from zid import zid

from app.config import OAUTH_SECRET_PREVIEW_LENGTH, TEST_USER_EMAIL_SUFFIX
from app.db import db, db_delete, db_insert
from app.lib.auth.context import auth_context
from app.lib.auth.crypto import hash_bytes
from app.lib.telemetry.testmethod import testmethod
from app.lib.text.locale import DEFAULT_LOCALE
from app.models.db.oauth2_application import OAuth2ApplicationInit, OAuth2Uri
from app.models.db.user import UserInit, user_is_test
from app.models.proto.admin_users_types import Role
from app.models.scope import PUBLIC_SCOPES, PublicScope
from app.models.types import ClientId, DisplayName, Email, LocaleCode, UserId


class TestService:
    @staticmethod
    @testmethod
    async def on_startup():
        """Prepare the test environment."""
        with auth_context(None):
            async with TaskGroup() as tg:
                tg.create_task(
                    TestService.create_user('admin', roles=['administrator'])
                )
                tg.create_task(
                    TestService.create_user('moderator', roles=['moderator'])
                )
                tg.create_task(TestService.create_user('user1'))
                tg.create_task(TestService.create_user('user2'))

            async with TaskGroup() as tg:
                tg.create_task(
                    TestService.create_oauth2_application(
                        name='TestApp',
                        client_id=ClientId('testapp'),
                        client_secret=None,
                        scopes=PUBLIC_SCOPES,
                        is_confidential=False,
                    )
                )
                tg.create_task(
                    TestService.create_oauth2_application(
                        name='TestApp-Minimal',
                        client_id=ClientId('testapp-minimal'),
                        client_secret=None,
                        scopes=frozenset(),
                        is_confidential=False,
                    )
                )
                tg.create_task(
                    TestService.create_oauth2_application(
                        name='TestApp-Secret',
                        client_id=ClientId('testapp-secret'),
                        client_secret='testapp.secret',  # noqa: S106
                        scopes=PUBLIC_SCOPES,
                        is_confidential=True,
                    )
                )

    @staticmethod
    @testmethod
    async def create_user(
        name: DisplayName | str,
        *,
        email_verified: bool = True,
        language: LocaleCode = DEFAULT_LOCALE,
        created_at: datetime | None = None,
        roles: list[Role] | None = None,
    ):
        """Create a test user."""
        user_init: UserInit = {
            'email': Email(f'{name}{TEST_USER_EMAIL_SUFFIX}'),
            'email_verified': email_verified,
            'display_name': name,  # type: ignore
            'language': language,
            'activity_tracking': False,
            'crash_reporting': False,
        }
        assert user_is_test(user_init), 'Test service must only create test users'

        try:
            async with db(True) as conn:
                row = await db_insert(
                    'user',
                    {
                        **user_init,
                        'roles': roles or [],
                        'created_at': t'COALESCE({created_at}, statement_timestamp())',
                    },
                    on_conflict=t"""(display_name) DO UPDATE SET
                        email = EXCLUDED.email,
                        email_verified = EXCLUDED.email_verified,
                        language = EXCLUDED.language,
                        roles = EXCLUDED.roles,
                        created_at = COALESCE({created_at}, "user".created_at)""",
                    returning='id',
                    conn=conn,
                )
                (user_id,) = row

                await db_delete(
                    'user_password',
                    where={'user_id': user_id},
                    conn=conn,
                )
        except UniqueViolation:
            pass

        logging.info('Upserted test user %r', name)

    @staticmethod
    @testmethod
    async def create_oauth2_application(
        *,
        name: str,
        client_id: ClientId,
        client_secret: str | None,
        scopes: frozenset[PublicScope],
        is_confidential: bool,
    ):
        """Create a test OAuth2 application."""
        app_init: OAuth2ApplicationInit = {
            'id': zid(),  # type: ignore
            'user_id': UserId(1),
            'name': name,
            'client_id': client_id,
        }

        client_secret_hashed = (
            hash_bytes(client_secret)  #
            if client_secret is not None
            else None
        )
        client_secret_preview = (
            client_secret[:OAUTH_SECRET_PREVIEW_LENGTH]
            if client_secret is not None
            else None
        )
        redirect_uris: list[OAuth2Uri] = [
            OAuth2Uri('http://localhost/callback'),
            OAuth2Uri('urn:ietf:wg:oauth:2.0:oob'),
        ]

        await db_insert(
            'oauth2_application',
            {
                **app_init,
                'client_secret_hashed': client_secret_hashed,
                'client_secret_preview': client_secret_preview,
                'confidential': is_confidential,
                'redirect_uris': redirect_uris,
                'scopes': sorted(scopes),
            },
            on_conflict=t"""(client_id) DO UPDATE SET
                name = EXCLUDED.name,
                client_secret_hashed = EXCLUDED.client_secret_hashed,
                client_secret_preview = EXCLUDED.client_secret_preview,
                confidential = EXCLUDED.confidential,
                redirect_uris = EXCLUDED.redirect_uris,
                scopes = EXCLUDED.scopes""",
        )

        logging.info('Upserted test OAuth2 application %r', name)
