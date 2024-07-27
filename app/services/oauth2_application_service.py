from sqlalchemy import delete, func, select, text, update

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_rand_urlsafe
from app.lib.crypto import encrypt
from app.lib.exceptions_context import raise_for
from app.lib.message_collector import MessageCollector
from app.lib.translation import t
from app.limits import OAUTH2_APP_USER_LIMIT
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.oauth2_token import OAuth2Token
from app.models.scope import Scope
from app.models.str import Uri


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
        user_id = auth_user(required=True).id
        client_id = buffered_rand_urlsafe(32)

        async with db_commit() as session:
            app = OAuth2Application(
                user_id=user_id,
                name=name,
                client_id=client_id,
                client_secret_encrypted=b'',
                scopes=scopes,
                is_confidential=is_confidential,
                redirect_uris=redirect_uris,
            )
            session.add(app)
            await session.flush()

            # check count after insert to prevent race conditions
            stmt = select(func.count()).select_from(
                select(text('1'))
                .where(
                    OAuth2Application.user_id == user_id,
                )
                .subquery()
            )
            count = (await session.execute(stmt)).scalar_one()
            if count > OAUTH2_APP_USER_LIMIT:
                MessageCollector.raise_error(None, t('validation.reached_oauth2_app_limit'))

        return app.id

    @staticmethod
    async def update_basic(
        *,
        app_id: int,
        redirect_uris: list[Uri],
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
