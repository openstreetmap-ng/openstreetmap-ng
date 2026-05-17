import logging
from asyncio import TaskGroup
from collections.abc import Iterable
from typing import Any

from pydantic import SecretStr
from zid import zid

from app.config import (
    OAUTH_APP_ADMIN_LIMIT,
    OAUTH_APP_URI_LIMIT,
    OAUTH_APP_URI_MAX_LENGTH,
    OAUTH_SECRET_PREVIEW_LENGTH,
)
from app.db import db, db_delete, db_fetchrow, db_update
from app.exceptions.context import raise_for
from app.lib.audit import audit
from app.lib.auth.context import auth_user
from app.lib.auth.crypto import hash_bytes
from app.lib.standard.feedback import StandardFeedback
from app.lib.storage import AVATAR_STORAGE
from app.lib.text.translation import t
from app.models.db.oauth2_application import (
    OAuth2Uri,
    oauth2_app_avatar_url,
)
from app.models.scope import PublicScope
from app.models.types import ApplicationId, ClientId, StorageKey
from app.services.image_service import ImageService
from app.validators.url import parse_uri
from speedup import buffered_rand_urlsafe


class OAuth2ApplicationService:
    @staticmethod
    async def create(*, name: str):
        """Create an OAuth2 application."""
        user_id = auth_user(required=True)['id']
        client_id = ClientId(buffered_rand_urlsafe(32))
        app_id: ApplicationId = zid()  # type: ignore

        async with db(True) as conn:
            row = await db_fetchrow(
                t"""
                    WITH app_count AS (
                        SELECT
                            -- Prevent count race conditions
                            pg_advisory_xact_lock(2847561039482756801::bigint # {user_id}),
                            COUNT(*) as cnt
                        FROM oauth2_application
                        WHERE user_id = {user_id}
                    )
                    INSERT INTO oauth2_application (id, user_id, name, client_id)
                    SELECT {app_id}, {user_id}, {name}, {client_id}
                    FROM app_count
                    WHERE app_count.cnt < {OAUTH_APP_ADMIN_LIMIT}
                    RETURNING id
                """,
                conn=conn,
            )

            if row is None:
                StandardFeedback.raise_error(None, t('validation.reached_app_limit'))

            await audit('create_app', conn, extra={'id': app_id, 'name': name})

        return app_id

    @staticmethod
    def validate_redirect_uris(redirect_uris: Iterable[str]) -> list[OAuth2Uri]:
        """Validate redirect URIs."""
        uris = [uri_ for uri in redirect_uris if (uri_ := uri.strip())]
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
                parsed_uri = parse_uri(uri)
            except Exception as exc:
                logging.debug('Invalid redirect URI %r', uri)
                StandardFeedback.raise_error(
                    'redirect_uris', t('validation.invalid_redirect_uri'), exc=exc
                )

            if parsed_uri.scheme == 'http' and parsed_uri.hostname not in {
                '127.0.0.1',
                'localhost',
                '::1',
            }:
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
        redirect_uris: list[OAuth2Uri],
        scopes: frozenset[PublicScope],
        revoke_all_authorizations: bool,
    ):
        """Update an OAuth2 application."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            row = await db_fetchrow(
                t"""
                    SELECT name, confidential, scopes
                    FROM oauth2_application
                    WHERE id = {app_id} AND user_id = {user_id}
                """,
                for_update=True,
                conn=conn,
            )
            if row is None:
                raise_for.unauthorized()
            old_name: str
            old_confidential: bool
            old_scopes: list[PublicScope]
            old_name, old_confidential, old_scopes = row

            scopes_list = sorted(scopes)
            await db_update(
                'oauth2_application',
                {
                    'name': name,
                    'confidential': is_confidential,
                    'redirect_uris': redirect_uris,
                    'scopes': scopes_list,
                    'updated_at': t'DEFAULT',
                },
                where={'id': app_id, 'user_id': user_id},
                conn=conn,
            )

            extra: dict[str, Any] = {'id': app_id}
            if old_name != name:
                extra['name'] = name
            if old_confidential != is_confidential:
                extra['confidential'] = is_confidential
            if scopes.symmetric_difference(old_scopes):
                extra['scopes'] = scopes_list
            if len(extra) > 1:
                await audit('change_app_settings', conn, extra=extra)

            if revoke_all_authorizations:
                rowcount = await db_delete(
                    'oauth2_token',
                    where={'application_id': app_id},
                    conn=conn,
                )
                if rowcount:
                    await audit('revoke_app_all_users', conn, extra={'id': app_id})

    @staticmethod
    async def update_avatar(app_id: ApplicationId, avatar_file: bytes):
        """Update app's avatar. Returns the new avatar URL."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            row = await db_fetchrow(
                t"""
                    SELECT avatar_id, client_id
                    FROM oauth2_application
                    WHERE id = {app_id} AND user_id = {user_id}
                """,
                for_update=True,
                conn=conn,
            )
            if row is None:
                raise_for.unauthorized()
            old_avatar_id: StorageKey | None
            client_id: ClientId
            old_avatar_id, client_id = row

            avatar_id = (
                await ImageService.upload_avatar(avatar_file) if avatar_file else None
            )

            await db_update(
                'oauth2_application',
                {'avatar_id': avatar_id, 'updated_at': t'DEFAULT'},
                where={'id': app_id, 'user_id': user_id},
                conn=conn,
            )

        if old_avatar_id is not None:
            async with TaskGroup() as tg:
                tg.create_task(AVATAR_STORAGE.delete(old_avatar_id))

        return oauth2_app_avatar_url({'avatar_id': avatar_id, 'client_id': client_id})  # type: ignore

    @staticmethod
    async def reset_client_secret(app_id: ApplicationId):
        """Reset the client secret and return the new one."""
        client_secret_ = buffered_rand_urlsafe(32)
        client_secret_hashed = hash_bytes(client_secret_)
        client_secret_preview = client_secret_[:OAUTH_SECRET_PREVIEW_LENGTH]
        client_secret = SecretStr(client_secret_)
        del client_secret_

        user_id = auth_user(required=True)['id']

        await db_update(
            'oauth2_application',
            {
                'client_secret_hashed': client_secret_hashed,
                'client_secret_preview': client_secret_preview,
                'updated_at': t'DEFAULT',
            },
            where={'id': app_id, 'user_id': user_id},
        )

        return client_secret

    @staticmethod
    async def delete(app_id: ApplicationId):
        """Delete an OAuth2 application."""
        user_id = auth_user(required=True)['id']

        await db_delete(
            'oauth2_application',
            where={'id': app_id, 'user_id': user_id},
        )
