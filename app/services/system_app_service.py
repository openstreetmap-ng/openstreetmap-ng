import logging
from asyncio import TaskGroup
from typing import NamedTuple

from pydantic import SecretStr
from zid import zid

from app.config import NAME
from app.db import db_insert
from app.exceptions.context import raise_for
from app.lib.auth.context import auth_user
from app.lib.auth.crypto import hash_bytes
from app.models.db.oauth2_application import (
    SYSTEM_APP_ID_CLIENT_ID,
    SYSTEM_APP_PAT_CLIENT_ID,
    SYSTEM_APP_RAPID_CLIENT_ID,
    SYSTEM_APP_WEB_CLIENT_ID,
    OAuth2ApplicationInit,
)
from app.models.db.oauth2_token import OAuth2TokenInit
from app.models.scope import PUBLIC_SCOPES, Scope
from app.models.types import ApplicationId, ClientId, OAuth2TokenId, UserId
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from speedup import buffered_rand_urlsafe

SYSTEM_APP_CLIENT_ID_MAP: dict[ClientId, ApplicationId] = {}
"""
Mapping of SystemApp client IDs to database IDs.
"""


class SystemApp(NamedTuple):
    name: str
    client_id: ClientId
    scopes: list[Scope]


class AccessTokenResult(NamedTuple):
    token: SecretStr
    token_id: OAuth2TokenId
    app_id: ApplicationId


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
    ):
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

        await db_insert(
            'oauth2_token',
            {**token_init, 'authorized_at': t'statement_timestamp()'},
        )

        logging.debug('Created %r access token for user %d', client_id, user_id)
        return AccessTokenResult(
            token=access_token,
            token_id=token_init['id'],
            app_id=app_id,
        )


async def _register_app(app: SystemApp):
    """Register a system app."""
    app_init: OAuth2ApplicationInit = {
        'id': zid(),  # type: ignore
        'user_id': None,
        'name': app.name,
        'client_id': app.client_id,
    }

    row = await db_insert(
        'oauth2_application',
        {
            **app_init,
            'scopes': sorted(app.scopes),
            'confidential': True,
            'redirect_uris': [],
        },
        on_conflict=t"""(client_id) DO UPDATE SET
            name = EXCLUDED.name,
            scopes = EXCLUDED.scopes""",
        returning='id',
    )
    app_id: ApplicationId = row[0]

    SYSTEM_APP_CLIENT_ID_MAP[app.client_id] = app_id
    logging.info('Registered system app %r', app.name)
