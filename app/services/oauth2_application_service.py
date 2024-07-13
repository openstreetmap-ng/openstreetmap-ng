from sqlalchemy import delete, update

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_rand_urlsafe
from app.lib.crypto import encrypt
from app.lib.exceptions_context import raise_for
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.oauth2_token import OAuth2Token
from app.models.scope import Scope


class OAuth2ApplicationService:
    @staticmethod
    async def create(
        *,
        name: str,
        scopes: tuple[Scope, ...],
        is_confidential: bool,
        redirect_uris: list[str],
    ) -> int:
        """
        Create an OAuth2 application.
        """
        client_id = buffered_rand_urlsafe(32)
        async with db_commit() as session:
            app = OAuth2Application(
                user_id=auth_user(required=True).id,
                name=name,
                client_id=client_id,
                client_secret_encrypted=b'',
                scopes=scopes,
                is_confidential=is_confidential,
                redirect_uris=redirect_uris,
            )
            session.add(app)
        return app.id

    @staticmethod
    async def update_basic(
        *,
        app_id: int,
        redirect_uris: list[str],
    ) -> None:
        """
        Update an OAuth2 application.
        """
        async with db_commit() as session:
            stmt = (
                update(OAuth2Application)
                .where(
                    OAuth2Application.id == app_id,
                    OAuth2Application.user_id == auth_user(required=True).id,
                )
                .values(
                    {
                        OAuth2Application.redirect_uris: redirect_uris,
                    }
                )
                .inline()
            )
            await session.execute(stmt)

    @staticmethod
    async def update_sensitive(
        *,
        app_id: int,
        name: str,
        scopes: tuple[Scope, ...],
        is_confidential: bool,
    ) -> None:
        """
        Update an OAuth2 application and revoke authenticated tokens.
        """
        async with db_commit() as session:
            stmt = (
                update(OAuth2Application)
                .where(
                    OAuth2Application.id == app_id,
                    OAuth2Application.user_id == auth_user(required=True).id,
                )
                .values(
                    {
                        OAuth2Application.name: name,
                        OAuth2Application.scopes: scopes,
                        OAuth2Application.is_confidential: is_confidential,
                    }
                )
                .inline()
            )
            result = await session.execute(stmt)
            if result.rowcount == 0:
                raise_for().unauthorized()

            await session.commit()
            stmt_delete = delete(OAuth2Token).where(OAuth2Token.application_id == app_id)
            await session.execute(stmt_delete)

    @staticmethod
    async def delete(app_id: int) -> None:
        """
        Delete an OAuth2 application.
        """
        async with db_commit() as session:
            stmt = delete(OAuth2Application).where(
                OAuth2Application.id == app_id,
                OAuth2Application.user_id == auth_user(required=True).id,
            )
            await session.execute(stmt)

    @staticmethod
    async def reset_client_secret(app_id: int) -> str:
        """
        Reset the client secret and return the new one.
        """
        client_secret = buffered_rand_urlsafe(32)
        client_secret_encrypted = encrypt(client_secret)
        async with db_commit() as session:
            stmt = (
                update(OAuth2Application)
                .where(
                    OAuth2Application.id == app_id,
                    OAuth2Application.user_id == auth_user(required=True).id,
                )
                .values(
                    {
                        OAuth2Application.client_secret_encrypted: client_secret_encrypted,
                    }
                )
            )
            await session.execute(stmt)
        return client_secret
