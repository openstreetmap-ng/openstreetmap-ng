import logging
from asyncio import TaskGroup
from typing import NamedTuple

from pydantic import SecretStr
from zid import zid

from app.config import NAME
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.models.db.oauth2_application import (
    SYSTEM_APP_ID_CLIENT_ID,
    SYSTEM_APP_PAT_CLIENT_ID,
    SYSTEM_APP_RAPID_CLIENT_ID,
    SYSTEM_APP_WEB_CLIENT_ID,
    OAuth2ApplicationInit,
)
from app.models.db.oauth2_token import OAuth2TokenInit
from app.models.scope import PUBLIC_SCOPES, Scope
from app.models.types import ApplicationId, ClientId, UserId
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from speedup.buffered_rand import buffered_rand_urlsafe

SYSTEM_APP_CLIENT_ID_MAP: dict[ClientId, ApplicationId] = {}
"""
Mapping of SystemApp client IDs to database IDs.
"""


class SystemApp(NamedTuple):
    name: str
    client_id: ClientId
    scopes: list[Scope]


class SystemAppService:
    @staticmethod
    async def on_startup():
        """Register and update system apps in the database."""
        async with TaskGroup() as tg:
            for app in (
                SystemApp(
                    name=NAME,
                    client_id=SYSTEM_APP_WEB_CLIENT_ID,
                    scopes=['web_user'],
                ),
                SystemApp(
                    name='Personal Access Token',
                    client_id=SYSTEM_APP_PAT_CLIENT_ID,
                    scopes=list(PUBLIC_SCOPES),
                ),
                SystemApp(
                    name='iD',
                    client_id=SYSTEM_APP_ID_CLIENT_ID,
                    scopes=[
                        'read_prefs',
                        'write_prefs',
                        'write_api',
                        'read_gpx',
                        'write_notes',
                    ],
                ),
                SystemApp(
                    name='Rapid',
                    client_id=SYSTEM_APP_RAPID_CLIENT_ID,
                    scopes=[
                        'read_prefs',
                        'write_prefs',
                        'write_api',
                        'read_gpx',
                        'write_notes',
                    ],
                ),
            ):
                tg.create_task(_register_app(app))

    @staticmethod
    async def create_access_token(
        client_id: ClientId, *, user_id: UserId | None = None, hidden: bool = False
    ) -> SecretStr:
        """Create an OAuth2-based access token for the given system app."""
        if user_id is None:
            user_id = auth_user(required=True)['id']

        app_id = SYSTEM_APP_CLIENT_ID_MAP.get(client_id)
        if app_id is None:
            raise_for.oauth_bad_client_id()

        app = await OAuth2ApplicationQuery.find_by_id(app_id)
        assert app is not None, f'OAuth2 application {client_id!r} must be initialized'

        access_token_ = buffered_rand_urlsafe(32)
        access_token_hashed = hash_bytes(access_token_)
        access_token = SecretStr(access_token_)
        del access_token_

        token_init: OAuth2TokenInit = {
            'id': zid(),  # type: ignore
            'user_id': user_id,
            'application_id': app_id,
            'unlisted': hidden,
            'name': None,
            'token_hashed': access_token_hashed,
            'token_preview': None,
            'redirect_uri': None,
            'scopes': app['scopes'],
            'code_challenge_method': None,
            'code_challenge': None,
        }

        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO oauth2_token (
                    id, user_id, application_id, unlisted, name,
                    token_hashed, token_preview, redirect_uri,
                    scopes, code_challenge_method, code_challenge,
                    authorized_at
                )
                VALUES (
                    %(id)s, %(user_id)s, %(application_id)s, %(unlisted)s, %(name)s,
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
    app_init: OAuth2ApplicationInit = {
        'id': zid(),  # type: ignore
        'user_id': None,
        'name': app.name,
        'client_id': app.client_id,
    }

    async with (
        db(True) as conn,
        await conn.execute(
            """
            INSERT INTO oauth2_application (
                id, user_id, name, client_id,
                scopes, confidential, redirect_uris
            )
            VALUES (
                %(id)s, %(user_id)s, %(name)s, %(client_id)s,
                %(scopes)s, %(confidential)s, %(redirect_uris)s
            )
            ON CONFLICT (client_id) DO UPDATE SET
                name = EXCLUDED.name,
                scopes = EXCLUDED.scopes
            RETURNING id
            """,
            {
                **app_init,
                'scopes': sorted(app.scopes),
                'confidential': True,
                'redirect_uris': [],
            },
        ) as r,
    ):
        app_id: ApplicationId = (await r.fetchone())[0]  # type: ignore

    SYSTEM_APP_CLIENT_ID_MAP[app.client_id] = app_id
    logging.info('Registered system app %r', app.name)
