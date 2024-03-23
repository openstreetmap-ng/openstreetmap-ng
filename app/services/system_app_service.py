import logging

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.db import db_autocommit
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_rand_urlsafe
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.oauth2_token import OAuth2Token
from app.models.system_app import SYSTEM_APPS
from app.repositories.oauth2_application_repository import OAuth2ApplicationRepository


class SystemAppService:
    @staticmethod
    async def on_startup():
        """
        Register and update system apps in the database.
        """
        async with db_autocommit() as session:
            for app in SYSTEM_APPS:
                logging.info('Registering system app %r', app.name)

                stmt = (
                    insert(OAuth2Application)
                    .values(
                        {
                            OAuth2Application.user_id: None,
                            OAuth2Application.name: app.name,
                            OAuth2Application.client_id: app.client_id,
                            OAuth2Application.client_secret_encrypted: b'',
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
                )

                await session.execute(stmt)

    @staticmethod
    async def create_access_token(client_id: str) -> str:
        """
        Create an access token for a system app.

        The access token can be used to make requests on behalf of the user.
        """

        app = await OAuth2ApplicationRepository.find_by_client_id(client_id)

        if app is None:
            raise_for().oauth_bad_app_client_id()
        if app.user_id is not None:
            raise_for().oauth_bad_app_client_id()

        access_token = buffered_rand_urlsafe(32)
        access_token_hashed = hash_bytes(access_token, context=None)

        async with db_autocommit() as session:
            token = OAuth2Token(
                user_id=auth_user().id,
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
