import logging
from asyncio import TaskGroup
from typing import NamedTuple

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.config import NAME
from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_rand_urlsafe
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.oauth2_token import OAuth2Token
from app.models.scope import PUBLIC_SCOPES, Scope
from app.queries.oauth2_application_query import OAuth2ApplicationQuery


class SystemApp(NamedTuple):
    name: str
    client_id: str
    scopes: tuple[Scope, ...]


class SystemAppService:
    @staticmethod
    async def on_startup():
        """
        Register and update system apps in the database.
        """
        async with TaskGroup() as tg:
            for app in (
                SystemApp(
                    name=NAME,
                    client_id='SystemApp.web',
                    scopes=(Scope.web_user,),
                ),
                SystemApp(
                    name='Personal Access Token',
                    client_id='SystemApp.pat',
                    scopes=PUBLIC_SCOPES,
                ),
                SystemApp(
                    name='iD',
                    client_id='SystemApp.id',
                    scopes=(
                        Scope.read_prefs,
                        Scope.write_prefs,
                        Scope.write_api,
                        Scope.read_gpx,
                        Scope.write_notes,
                    ),
                ),
                SystemApp(
                    name='Rapid',
                    client_id='SystemApp.rapid',
                    scopes=(
                        Scope.read_prefs,
                        Scope.write_prefs,
                        Scope.write_api,
                        Scope.read_gpx,
                        Scope.write_notes,
                    ),
                ),
            ):
                tg.create_task(_register_app(app))

    @staticmethod
    async def create_access_token(client_id: str, *, user_id: int | None = None) -> str:
        """
        Create an OAuth2-based access token for a system app.
        """
        if user_id is None:
            user_id = auth_user(required=True).id

        app = await OAuth2ApplicationQuery.find_one_by_client_id(client_id)
        if app is None or not app.is_system_app:
            raise_for().oauth_bad_client_id()

        access_token = buffered_rand_urlsafe(32)
        access_token_hashed = hash_bytes(access_token)
        async with db_commit() as session:
            token = OAuth2Token(
                user_id=user_id,
                application_id=app.id,
                token_hashed=access_token_hashed,
                scopes=app.scopes,
                redirect_uri=None,
                code_challenge_method=None,
                code_challenge=None,
            )
            token.authorized_at = func.statement_timestamp()
            session.add(token)
        return access_token


async def _register_app(app: SystemApp) -> None:
    """
    Register a system app.
    """
    logging.info('Registering system app %r', app.name)
    async with db_commit() as session:
        stmt = (
            insert(OAuth2Application)
            .values(
                {
                    OAuth2Application.user_id: None,
                    OAuth2Application.name: app.name,
                    OAuth2Application.client_id: app.client_id,
                    OAuth2Application.scopes: app.scopes,
                    OAuth2Application.is_confidential: True,
                    OAuth2Application.redirect_uris: (),
                }
            )
            .on_conflict_do_update(
                index_elements=(OAuth2Application.client_id,),
                set_={
                    OAuth2Application.name: app.name,
                    OAuth2Application.scopes: app.scopes,
                },
            )
            .inline()
        )
        await session.execute(stmt)
