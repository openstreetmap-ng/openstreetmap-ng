import logging
from asyncio import TaskGroup

from fastapi import UploadFile
from pydantic import SecretStr
from rfc3986 import uri_reference
from zid import zid

from app.config import (
    OAUTH_APP_ADMIN_LIMIT,
    OAUTH_APP_URI_LIMIT,
    OAUTH_APP_URI_MAX_LENGTH,
    OAUTH_SECRET_PREVIEW_LENGTH,
)
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.db.oauth2_application import (
    OAuth2ApplicationInit,
    oauth2_app_avatar_url,
)
from app.models.scope import PublicScope
from app.models.types import ApplicationId, ClientId, StorageKey, Uri
from app.services.image_service import ImageService
from app.utils import splitlines_trim
from app.validators.url import UriValidator
from speedup.buffered_rand import buffered_rand_urlsafe


class OAuth2ApplicationService:
    @staticmethod
    async def create(*, name: str) -> ApplicationId:
        """Create an OAuth2 application."""
        user_id = auth_user(required=True)['id']
        client_id = ClientId(buffered_rand_urlsafe(32))

        app_id: ApplicationId = zid()  # type: ignore
        app_init: OAuth2ApplicationInit = {
            'id': app_id,
            'user_id': user_id,
            'name': name,
            'client_id': client_id,
        }

        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO oauth2_application (
                    id, user_id, name, client_id
                )
                VALUES (
                    %(id)s, %(user_id)s, %(name)s, %(client_id)s
                )
                """,
                app_init,
            )

            # Check count after insert to prevent race conditions
            async with await conn.execute(
                """
                SELECT COUNT(*) FROM oauth2_application
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r:
                count: int = (await r.fetchone())[0]  # type: ignore
                if count > OAUTH_APP_ADMIN_LIMIT:
                    StandardFeedback.raise_error(
                        None, t('validation.reached_app_limit')
                    )

        return app_id

    @staticmethod
    def validate_redirect_uris(redirect_uris: str) -> list[Uri]:
        """Validate redirect URIs."""
        uris = splitlines_trim(redirect_uris)
        if len(uris) > OAUTH_APP_URI_LIMIT:
            StandardFeedback.raise_error(
                'redirect_uris', t('validation.too_many_redirect_uris')
            )

        for uri in uris:
            if len(uri) > OAUTH_APP_URI_MAX_LENGTH:
                StandardFeedback.raise_error(
                    'redirect_uris', t('validation.redirect_uri_too_long')
                )

            if uri in {'urn:ietf:wg:oauth:2.0:oob', 'urn:ietf:wg:oauth:2.0:oob:auto'}:
                continue

            try:
                UriValidator.validate(uri_reference(uri))
            except Exception:
                logging.debug('Invalid redirect URI %r', uri)
                StandardFeedback.raise_error(
                    'redirect_uris', t('validation.invalid_redirect_uri')
                )

            normalized = f'{uri.casefold()}/'
            if normalized.startswith('http://') and not normalized.startswith((
                'http://127.0.0.1/',
                'http://localhost/',
            )):
                StandardFeedback.raise_error(
                    'redirect_uris', t('validation.insecure_redirect_uri')
                )

        # deduplicate (order-preserving) and cast type
        return list(dict.fromkeys(uris))  # type: ignore

    @staticmethod
    async def update_settings(
        *,
        app_id: ApplicationId,
        name: str,
        is_confidential: bool,
        redirect_uris: list[Uri],
        scopes: tuple[PublicScope, ...],
        revoke_all_authorizations: bool,
    ) -> None:
        """Update an OAuth2 application."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            result = await conn.execute(
                """
                UPDATE oauth2_application
                SET
                    name = %s,
                    confidential = %s,
                    redirect_uris = %s,
                    scopes = %s,
                    updated_at = DEFAULT
                WHERE id = %s AND user_id = %s
                """,
                (name, is_confidential, redirect_uris, list(scopes), app_id, user_id),
            )

            if not result.rowcount:
                raise_for.unauthorized()

            if revoke_all_authorizations:
                await conn.execute(
                    """
                    DELETE FROM oauth2_token
                    WHERE application_id = %s
                    """,
                    (app_id,),
                )

    @staticmethod
    async def update_avatar(app_id: ApplicationId, avatar_file: UploadFile) -> str:
        """Update app's avatar. Returns the new avatar URL."""
        data = await avatar_file.read()
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT avatar_id, client_id
                FROM oauth2_application
                WHERE id = %s AND user_id = %s
                FOR UPDATE
                """,
                (app_id, user_id),
            ) as r:
                row = await r.fetchone()
                if row is None:
                    raise_for.unauthorized()
                old_avatar_id: StorageKey | None
                client_id: ClientId
                old_avatar_id, client_id = row

            avatar_id = await ImageService.upload_avatar(data) if data else None

            await conn.execute(
                """
                UPDATE oauth2_application
                SET
                    avatar_id = %s,
                    updated_at = DEFAULT
                WHERE id = %s AND user_id = %s
                """,
                (avatar_id, app_id, user_id),
            )

        if old_avatar_id is not None:
            async with TaskGroup() as tg:
                tg.create_task(ImageService.delete_avatar_by_id(old_avatar_id))

        return oauth2_app_avatar_url({'avatar_id': avatar_id, 'client_id': client_id})  # type: ignore

    @staticmethod
    async def reset_client_secret(app_id: ApplicationId) -> SecretStr:
        """Reset the client secret and return the new one."""
        client_secret_ = buffered_rand_urlsafe(32)
        client_secret_hashed = hash_bytes(client_secret_)
        client_secret_preview = client_secret_[:OAUTH_SECRET_PREVIEW_LENGTH]
        client_secret = SecretStr(client_secret_)
        del client_secret_

        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await conn.execute(
                """
                UPDATE oauth2_application
                SET
                    client_secret_hashed = %s,
                    client_secret_preview = %s,
                    updated_at = DEFAULT
                WHERE id = %s AND user_id = %s
                """,
                (client_secret_hashed, client_secret_preview, app_id, user_id),
            )

        return client_secret

    @staticmethod
    async def delete(app_id: ApplicationId) -> None:
        """Delete an OAuth2 application."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await conn.execute(
                """
                DELETE FROM oauth2_application
                WHERE id = %s AND user_id = %s
                """,
                (app_id, user_id),
            )
