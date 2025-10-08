import logging
from asyncio import TaskGroup
from datetime import datetime

from zid import zid

from app.config import OAUTH_SECRET_PREVIEW_LENGTH, TEST_USER_EMAIL_SUFFIX
from app.db import db
from app.lib.auth_context import auth_context
from app.lib.crypto import hash_bytes
from app.lib.locale import DEFAULT_LOCALE
from app.lib.testmethod import testmethod
from app.models.db.oauth2_application import OAuth2ApplicationInit, OAuth2Uri
from app.models.db.user import UserInit, UserRole, user_is_test
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
        roles: list[UserRole] | None = None,
    ) -> None:
        """Create a test user."""
        user_init: UserInit = {
            'email': Email(f'{name}{TEST_USER_EMAIL_SUFFIX}'),
            'email_verified': email_verified,
            'display_name': name,  # type: ignore
            'password_pb': b'',
            'language': language,
            'activity_tracking': False,
            'crash_reporting': False,
        }
        assert user_is_test(user_init), 'Test service must only create test users'

        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO "user" (
                    email, email_verified, display_name, password_pb,
                    language, activity_tracking, crash_reporting,
                    roles, created_at
                )
                VALUES (
                    %(email)s, %(email_verified)s, %(display_name)s, %(password_pb)s,
                    %(language)s, %(activity_tracking)s, %(crash_reporting)s,
                    %(roles)s, COALESCE(%(created_at)s, statement_timestamp())
                )
                ON CONFLICT (display_name) DO UPDATE SET
                    email = EXCLUDED.email,
                    email_verified = EXCLUDED.email_verified,
                    password_pb = EXCLUDED.password_pb,
                    language = EXCLUDED.language,
                    roles = EXCLUDED.roles,
                    created_at = COALESCE(%(created_at)s, "user".created_at)
                """,
                {
                    **user_init,
                    'roles': roles or [],
                    'created_at': created_at,
                },
            )

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
    ) -> None:
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

        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO oauth2_application (
                    id, user_id, name, client_id,
                    client_secret_hashed, client_secret_preview,
                    confidential, redirect_uris, scopes
                )
                VALUES (
                    %(id)s, %(user_id)s, %(name)s, %(client_id)s,
                    %(client_secret_hashed)s, %(client_secret_preview)s,
                    %(confidential)s, %(redirect_uris)s, %(scopes)s
                )
                ON CONFLICT (client_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    client_secret_hashed = EXCLUDED.client_secret_hashed,
                    client_secret_preview = EXCLUDED.client_secret_preview,
                    confidential = EXCLUDED.confidential,
                    redirect_uris = EXCLUDED.redirect_uris,
                    scopes = EXCLUDED.scopes
                """,
                {
                    **app_init,
                    'client_secret_hashed': client_secret_hashed,
                    'client_secret_preview': client_secret_preview,
                    'confidential': is_confidential,
                    'redirect_uris': redirect_uris,
                    'scopes': sorted(scopes),
                },
            )

        logging.info('Upserted test OAuth2 application %r', name)
