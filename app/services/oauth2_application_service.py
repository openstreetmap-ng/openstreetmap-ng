import logging

from fastapi import UploadFile
from pydantic import SecretStr
from rfc3986 import uri_reference
from sqlalchemy import delete, func, select, text, update

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_rand_urlsafe
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.limits import (
    OAUTH_APP_ADMIN_LIMIT,
    OAUTH_APP_URI_LIMIT,
    OAUTH_APP_URI_MAX_LENGTH,
    OAUTH_SECRET_PREVIEW_LENGTH,
)
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.oauth2_token import OAuth2Token
from app.models.scope import Scope
from app.models.types import Uri
from app.services.image_service import ImageService
from app.utils import splitlines_trim
from app.validators.url import UriValidator


class OAuth2ApplicationService:
    @staticmethod
    async def create(*, name: str) -> int:
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
                scopes=(),
                is_confidential=False,
                redirect_uris=(),
            )
            session.add(app)
            await session.flush()

            # check count after insert to prevent race conditions
            stmt = select(func.count()).select_from(
                select(text('1'))  #
                .where(OAuth2Application.user_id == user_id)
                .subquery()
            )
            count = (await session.execute(stmt)).scalar_one()
            if count > OAUTH_APP_ADMIN_LIMIT:
                StandardFeedback.raise_error(None, t('validation.reached_app_limit'))

        return app.id

    @staticmethod
    def validate_redirect_uris(redirect_uris: str) -> tuple[Uri, ...]:
        uris = splitlines_trim(redirect_uris)
        if len(uris) > OAUTH_APP_URI_LIMIT:
            StandardFeedback.raise_error('redirect_uris', t('validation.too_many_redirect_uris'))
        for uri in uris:
            if len(uri) > OAUTH_APP_URI_MAX_LENGTH:
                StandardFeedback.raise_error('redirect_uris', t('validation.redirect_uri_too_long'))
            if uri in {'urn:ietf:wg:oauth:2.0:oob', 'urn:ietf:wg:oauth:2.0:oob:auto'}:
                continue
            try:
                UriValidator.validate(uri_reference(uri))
            except Exception:
                logging.debug('Invalid redirect URI %r', uri)
                StandardFeedback.raise_error('redirect_uris', t('validation.invalid_redirect_uri'))
            normalized = f'{uri.casefold()}/'
            if normalized.startswith('http://') and not normalized.startswith(
                ('http://127.0.0.1/', 'http://localhost/')
            ):
                StandardFeedback.raise_error('redirect_uris', t('validation.insecure_redirect_uri'))
        # deduplicate (order-preserving) and cast type
        return tuple({Uri(uri): None for uri in uris})

    @staticmethod
    async def update_settings(
        *,
        app_id: int,
        name: str,
        is_confidential: bool,
        redirect_uris: tuple[Uri, ...],
        scopes: tuple[Scope, ...],
        revoke_all_authorizations: bool,
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
                        OAuth2Application.name: name,
                        OAuth2Application.is_confidential: is_confidential,
                        OAuth2Application.redirect_uris: redirect_uris,
                        OAuth2Application.scopes: scopes,
                    }
                )
                .inline()
            )
            result = await session.execute(stmt)
            if not result.rowcount:
                raise_for.unauthorized()

            if revoke_all_authorizations:
                await session.commit()
                await session.execute(delete(OAuth2Token).where(OAuth2Token.application_id == app_id))

    @staticmethod
    async def update_avatar(app_id: int, avatar_file: UploadFile) -> str:
        """
        Update app's avatar.

        Returns the new avatar URL.
        """
        data = await avatar_file.read()
        avatar_id = await ImageService.upload_avatar(data) if data else None

        # update app data
        async with db_commit() as session:
            stmt = (
                select(OAuth2Application)
                .where(
                    OAuth2Application.id == app_id,
                    OAuth2Application.user_id == auth_user(required=True).id,
                )
                .with_for_update()
            )
            app = await session.scalar(stmt)
            if app is None:
                raise_for.unauthorized()

            old_avatar_id = app.avatar_id
            app.avatar_id = avatar_id

        # cleanup old avatar
        if old_avatar_id is not None:
            await ImageService.delete_avatar_by_id(old_avatar_id)

        return app.avatar_url

    @staticmethod
    async def reset_client_secret(app_id: int) -> SecretStr:
        """
        Reset the client secret and return the new one.
        """
        client_secret = buffered_rand_urlsafe(32)
        client_secret_hashed = hash_bytes(client_secret)
        async with db_commit() as session:
            stmt = (
                update(OAuth2Application)
                .where(
                    OAuth2Application.id == app_id,
                    OAuth2Application.user_id == auth_user(required=True).id,
                )
                .values(
                    {
                        OAuth2Application.client_secret_hashed: client_secret_hashed,
                        OAuth2Application.client_secret_preview: client_secret[:OAUTH_SECRET_PREVIEW_LENGTH],
                    }
                )
                .inline()
            )
            await session.execute(stmt)
        return SecretStr(client_secret)

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
