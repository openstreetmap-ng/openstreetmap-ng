import logging
from asyncio import TaskGroup
from typing import NamedTuple

from pydantic import SecretStr

from app.config import NAME
from app.db import db2
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_rand_urlsafe
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.models.db.oauth2_application import ApplicationId, ClientId, OAuth2ApplicationInit
from app.models.db.oauth2_token import OAuth2TokenInit
from app.models.db.user import UserId
from app.models.scope import PUBLIC_SCOPES, Scope
from app.queries.oauth2_application_query import OAuth2ApplicationQuery

SYSTEM_APP_CLIENT_ID_MAP: dict[ClientId, ApplicationId] = {}
"""
Mapping of SystemApp client IDs to database IDs.
"""


class SystemApp(NamedTuple):
    name: str
    client_id: ClientId
    scopes: tuple[Scope, ...]


class SystemAppService:
    @staticmethod
    async def on_startup():
        """Register and update system apps in the database."""
        async with TaskGroup() as tg:
            for app in (
                SystemApp(
                    name=NAME,
                    client_id=ClientId('SystemApp.web'),
                    scopes=('web_user',),
                ),
                SystemApp(
                    name='Personal Access Token',
                    client_id=ClientId('SystemApp.pat'),
                    scopes=tuple(PUBLIC_SCOPES),
                ),
                SystemApp(
                    name='iD',
                    client_id=ClientId('SystemApp.id'),
                    scopes=(
                        'read_prefs',
                        'write_prefs',
                        'write_api',
                        'read_gpx',
                        'write_notes',
                    ),
                ),
                SystemApp(
                    name='Rapid',
                    client_id=ClientId('SystemApp.rapid'),
                    scopes=(
                        'read_prefs',
                        'write_prefs',
                        'write_api',
                        'read_gpx',
                        'write_notes',
                    ),
                ),
            ):
                tg.create_task(_register_app(app))

    @staticmethod
    async def create_access_token(client_id: ClientId, *, user_id: UserId | None = None) -> SecretStr:
        """Create an OAuth2-based access token for the given system app."""
        if user_id is None:
            user_id = auth_user(required=True)['id']

        app_id = SYSTEM_APP_CLIENT_ID_MAP.get(client_id)
        if app_id is None:
            raise_for.oauth_bad_client_id()

        app = await OAuth2ApplicationQuery.find_one_by_id(app_id)
        assert app is not None, f'OAuth2 application {client_id!r} must be initialized'

        access_token_ = buffered_rand_urlsafe(32)
        access_token_hashed = hash_bytes(access_token_)
        access_token = SecretStr(access_token_)
        del access_token_

        token_init: OAuth2TokenInit = {
            'user_id': user_id,
            'application_id': app_id,
            'name': None,
            'token_hashed': access_token_hashed,
            'token_preview': None,
            'redirect_uri': None,
            'scopes': app['scopes'],
            'code_challenge_method': None,
            'code_challenge': None,
        }

        async with db2(True) as conn:
            await conn.execute(
                """
                INSERT INTO oauth2_token (
                    user_id, application_id, name,
                    token_hashed, token_preview, redirect_uri,
                    scopes, code_challenge_method, code_challenge,
                    authorized_at
                )
                VALUES (
                    %(user_id)s, %(application_id)s, %(name)s,
                    %(token_hashed)s, %(token_preview)s, %(redirect_uri)s,
                    %(scopes)s, %(code_challenge_method)s, %(code_challenge)s,
                    statement_timestamp()
                )
                """,
                token_init,
            )

        logging.debug('Created %r access token for user %d', client_id, user_id)
        return access_token


async def _register_app(app: SystemApp) -> None:
    """Register a system app."""
    logging.info('Registering system app %r', app.name)

    app_init: OAuth2ApplicationInit = {
        'user_id': None,
        'name': app.name,
        'client_id': app.client_id,
    }

    async with (
        db2(True) as conn,
        await conn.execute(
            """
            INSERT INTO oauth2_application (
                user_id, name, client_id,
                scopes, confidential, redirect_uris
            )
            VALUES (
                %(user_id)s, %(name)s, %(client_id)s,
                %(scopes)s, %(confidential)s, %(redirect_uris)s
            )
            ON CONFLICT (client_id) DO UPDATE
            SET
                name = EXCLUDED.name,
                scopes = EXCLUDED.scopes
            RETURNING id
            """,
            {
                **app_init,
                'scopes': app.scopes,
                'confidential': True,
                'redirect_uris': [],
            },
        ) as r,
    ):
        app_id: ApplicationId = (await r.fetchone())[0]  # type: ignore
        SYSTEM_APP_CLIENT_ID_MAP[app.client_id] = app_id
