import logging
from datetime import datetime
from random import random
from typing import Literal, assert_never, overload

from psycopg import AsyncConnection
from pydantic import SecretStr
from zid import zid

from app.config import (
    OAUTH2_TOKEN_CLEANUP_PROBABILITY,
    OAUTH_AUTHORIZATION_CODE_TIMEOUT,
    OAUTH_SECRET_PREVIEW_LENGTH,
    OAUTH_SILENT_AUTH_QUERY_SESSION_LIMIT,
)
from app.db import db, db_delete, db_fetchone, db_insert, db_update
from app.exceptions.context import raise_for
from app.lib.audit import audit
from app.lib.auth.context import auth_user
from app.lib.auth.crypto import hash_bytes, hash_compare, hash_s256_code_challenge
from app.models.db.oauth2_application import (
    SYSTEM_APP_PAT_CLIENT_ID,
    OAuth2Application,
    OAuth2Uri,
    oauth2_app_is_system,
)
from app.models.db.oauth2_token import (
    OAuth2CodeChallengeMethod,
    OAuth2Token,
    OAuth2TokenInit,
    OAuth2TokenOOB,
    oauth2_token_is_oob,
)
from app.models.scope import PublicScope
from app.models.types import ApplicationId, ClientId, OAuth2TokenId, UserId
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.services.system_app_service import SYSTEM_APP_CLIENT_ID_MAP
from speedup import buffered_rand_urlsafe

# TODO: limit number of access tokens per user+app


class OAuth2TokenService:
    @staticmethod
    @overload
    async def authorize(
        *,
        init: Literal[False],
        client_id: ClientId,
        redirect_uri: OAuth2Uri,
        scopes: frozenset[PublicScope],
        code_challenge_method: OAuth2CodeChallengeMethod | None,
        code_challenge: str | None,
        state: str | None,
    ) -> dict[str, str] | OAuth2TokenOOB: ...
    @staticmethod
    @overload
    async def authorize(
        *,
        init: bool,
        client_id: ClientId,
        redirect_uri: OAuth2Uri,
        scopes: frozenset[PublicScope],
        code_challenge_method: OAuth2CodeChallengeMethod | None,
        code_challenge: str | None,
        state: str | None,
    ) -> dict[str, str] | OAuth2TokenOOB | OAuth2Application: ...
    @staticmethod
    async def authorize(
        *,
        init: bool,
        client_id: ClientId,
        redirect_uri: OAuth2Uri,
        scopes: frozenset[PublicScope],
        code_challenge_method: OAuth2CodeChallengeMethod | None,
        code_challenge: str | None,
        state: str | None,
    ):
        """
        Create a new authorization code.

        The code can be exchanged for an access token.

        In init=True mode, silent authentication is performed if the application is already authorized.
        When successful, an authorization code is returned.
        Otherwise, the application instance is returned for the user to authorize it.

        In init=False mode, an authorization code is returned.
        """
        if (code_challenge_method is None) != (code_challenge is None):
            raise_for.oauth2_bad_code_challenge_params()

        user_id = auth_user(required=True)['id']

        app = await OAuth2ApplicationQuery.find_by_client_id(client_id)
        if app is None or oauth2_app_is_system(app):
            raise_for.oauth_bad_client_id()

        if redirect_uri not in app['redirect_uris']:
            raise_for.oauth_bad_redirect_uri()

        if not scopes.issubset(app['scopes']):
            raise_for.oauth_bad_scopes()

        if init:
            tokens = await OAuth2TokenQuery.find_authorized_by_user_app_id(
                user_id=user_id,
                app_id=app['id'],
                limit=OAUTH_SILENT_AUTH_QUERY_SESSION_LIMIT,
            )

            for token in tokens:
                # Ignore different redirect URI
                if token['redirect_uri'] != redirect_uri:
                    continue
                # Ignore different scopes
                if scopes.symmetric_difference(token['scopes']):
                    continue
                # Session found, auto-approve
                break
            else:
                # No session found, require manual approval
                return app

        authorization_code = buffered_rand_urlsafe(32)
        authorization_code_hashed = hash_bytes(authorization_code)

        token_init: OAuth2TokenInit = {
            'id': zid(),  # type: ignore
            'user_id': user_id,
            'application_id': app['id'],
            'unlisted': False,
            'name': None,
            'token_hashed': authorization_code_hashed,
            'token_preview': None,
            'redirect_uri': redirect_uri,
            'scopes': sorted(scopes),
            'code_challenge_method': code_challenge_method,
            'code_challenge': code_challenge,
        }

        await db_insert('oauth2_token', token_init)

        # Check if this is an OOB (out-of-band) token
        if oauth2_token_is_oob(redirect_uri):
            return OAuth2TokenOOB(authorization_code, state)

        params = {'code': authorization_code}
        if state is not None:
            params['state'] = state
        return params

    @staticmethod
    async def token(
        *,
        client_id: ClientId,
        client_secret: SecretStr | None,
        authorization_code: str,
        verifier: str | None,
        redirect_uri: OAuth2Uri,
    ):
        """
        Exchange an authorization code for an access token.
        The access token can be used to make requests on behalf of the user.
        """
        app = await OAuth2ApplicationQuery.find_by_client_id(client_id)
        if app is None or oauth2_app_is_system(app):
            raise_for.oauth_bad_client_id()

        # Check client credentials for confidential apps
        if app['confidential'] and (
            client_secret is None
            or app['client_secret_hashed'] is None
            or not hash_compare(
                client_secret.get_secret_value(), app['client_secret_hashed']
            )
        ):
            raise_for.oauth_bad_client_secret()

        authorization_code_hashed = hash_bytes(authorization_code)

        async with db(True) as conn:
            token = await db_fetchone(
                OAuth2Token,
                t"""
                    SELECT * FROM oauth2_token
                    WHERE token_hashed = {authorization_code_hashed}
                    AND created_at > statement_timestamp() - {OAUTH_AUTHORIZATION_CODE_TIMEOUT}
                    AND authorized_at IS NULL
                    FOR UPDATE
                """,
                conn=conn,
            )
            if token is None:
                raise_for.oauth_bad_user_token()

            try:
                # Verify redirect URI
                if token['redirect_uri'] != redirect_uri:
                    raise_for.oauth_bad_redirect_uri()

                # Verify code challenge
                code_challenge_method = token['code_challenge_method']
                if code_challenge_method is None:
                    if verifier is not None:
                        raise_for.oauth2_challenge_method_not_set()
                elif code_challenge_method == 'plain':
                    if token['code_challenge'] != verifier:
                        raise_for.oauth2_bad_verifier(code_challenge_method)
                elif code_challenge_method == 'S256':
                    if (
                        verifier is None  #
                        or token['code_challenge'] != hash_s256_code_challenge(verifier)
                    ):
                        raise_for.oauth2_bad_verifier(code_challenge_method)
                else:
                    assert_never(code_challenge_method)

            except Exception:
                # Delete the token if verification fails
                token_id = token['id']
                await db_delete('oauth2_token', where={'id': token_id}, conn=conn)
                raise

            access_token = buffered_rand_urlsafe(32)
            access_token_hashed = hash_bytes(access_token)
            token_id = token['id']

            row = await db_update(
                'oauth2_token',
                {
                    'token_hashed': access_token_hashed,
                    'authorized_at': t'statement_timestamp()',
                    'redirect_uri': None,
                    'code_challenge_method': None,
                    'code_challenge': None,
                },
                where={'id': token_id},
                returning='authorized_at',
                conn=conn,
            )
            authorized_at: datetime = row[0]

            await audit(
                'authorize_app',
                conn,
                extra={'id': app['id'], 'redirect_uri': redirect_uri},
            )

            # probabilistic cleanup of stale unauthorized tokens
            if random() < OAUTH2_TOKEN_CLEANUP_PROBABILITY:
                await _delete_stale_unauthorized(conn)

        return {
            'access_token': access_token,
            'token_type': 'Bearer',
            'scope': ' '.join(token['scopes']),
            'created_at': int(authorized_at.timestamp()),
            # TODO: id_token
        }

    @staticmethod
    async def create_pat(*, name: str, scopes: frozenset[PublicScope]):
        """Create a new Personal Access Token with the given name and scopes."""
        app_id = SYSTEM_APP_CLIENT_ID_MAP[SYSTEM_APP_PAT_CLIENT_ID]
        user_id = auth_user(required=True)['id']

        token_id: OAuth2TokenId = zid()  # type: ignore
        token_init: OAuth2TokenInit = {
            'id': token_id,
            'user_id': user_id,
            'application_id': app_id,
            'unlisted': False,
            'name': name,
            'token_hashed': None,
            'token_preview': None,
            'redirect_uri': None,
            'scopes': sorted(scopes),
            'code_challenge_method': None,
            'code_challenge': None,
        }

        async with db(True) as conn:
            await db_insert('oauth2_token', token_init, conn=conn)

            await audit(
                'create_pat',
                conn,
                extra={'id': token_id, 'name': name, 'scopes': token_init['scopes']},
            )

        return token_id

    @staticmethod
    async def reset_pat_access_token(pat_id: OAuth2TokenId):
        """Reset the personal access token and return the new secret."""
        app_id = SYSTEM_APP_CLIENT_ID_MAP[SYSTEM_APP_PAT_CLIENT_ID]
        access_token_ = buffered_rand_urlsafe(32)
        access_token_hashed = hash_bytes(access_token_)
        access_token_preview = access_token_[:OAUTH_SECRET_PREVIEW_LENGTH]
        access_token = SecretStr(access_token_)
        del access_token_
        user_id = auth_user(required=True)['id']

        await db_update(
            'oauth2_token',
            {
                'token_hashed': access_token_hashed,
                'token_preview': access_token_preview,
                'authorized_at': t'statement_timestamp()',
            },
            where={'id': pat_id, 'user_id': user_id, 'application_id': app_id},
        )

        return access_token

    @staticmethod
    async def revoke_by_id(token_id: OAuth2TokenId):
        """Revoke the given token by id."""
        user_id = auth_user(required=True)['id']

        await db_delete(
            'oauth2_token',
            where={'id': token_id, 'user_id': user_id},
        )

        logging.debug('Revoked OAuth2 token %d', token_id)

    @staticmethod
    async def revoke_by_access_token(access_token: SecretStr):
        """Revoke the given access token."""
        access_token_hashed = hash_bytes(access_token.get_secret_value())

        await db_delete(
            'oauth2_token',
            where={'token_hashed': access_token_hashed},
        )

        logging.debug('Revoked OAuth2 access token')

    @staticmethod
    async def revoke_by_app_id(
        app_id: ApplicationId,
        *,
        user_id: UserId | None = None,
        skip_ids: list[OAuth2TokenId] | None = None,
    ):
        """Revoke all current user tokens for the given OAuth2 application."""
        if user_id is None:
            user_id = auth_user(required=True)['id']

        where = (
            t'user_id = {user_id} AND application_id = {app_id} AND NOT (id = ANY({skip_ids}))'
            if skip_ids is not None
            else t'user_id = {user_id} AND application_id = {app_id}'
        )

        async with db(True) as conn:
            rowcount = await db_delete('oauth2_token', where=where, conn=conn)
            if rowcount:
                await audit('revoke_app', conn, extra={'id': app_id})

    @staticmethod
    async def revoke_by_client_id(
        client_id: ClientId,
        *,
        user_id: UserId | None = None,
        skip_ids: list[OAuth2TokenId] | None = None,
    ):
        """Revoke all current user tokens for the given OAuth2 client."""
        app = await db_fetchone(
            OAuth2Application,
            t'SELECT id FROM oauth2_application WHERE client_id = {client_id}',
        )

        if app is not None:
            await OAuth2TokenService.revoke_by_app_id(
                app['id'], user_id=user_id, skip_ids=skip_ids
            )


async def _delete_stale_unauthorized(conn: AsyncConnection):
    pat_app_id = SYSTEM_APP_CLIENT_ID_MAP[SYSTEM_APP_PAT_CLIENT_ID]
    rowcount = await db_delete(
        'oauth2_token',
        where=t"""authorized_at IS NULL
            AND application_id != {pat_app_id}
            AND created_at < statement_timestamp() - {OAUTH_AUTHORIZATION_CODE_TIMEOUT}""",
        conn=conn,
    )
    if rowcount:
        logging.debug('Deleted %d stale unauthorized OAuth2 tokens', rowcount)
