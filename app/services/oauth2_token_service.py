import logging
from datetime import datetime
from typing import Any, Literal, overload

from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable
from pydantic import SecretStr
from zid import zid

from app.config import (
    OAUTH_AUTHORIZATION_CODE_TIMEOUT,
    OAUTH_SECRET_PREVIEW_LENGTH,
    OAUTH_SILENT_AUTH_QUERY_SESSION_LIMIT,
)
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.crypto import hash_bytes, hash_compare, hash_s256_code_challenge
from app.lib.exceptions_context import raise_for
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
from speedup.buffered_rand import buffered_rand_urlsafe

# TODO: limit number of access tokens per user+app


class OAuth2TokenService:
    @staticmethod
    @overload
    async def authorize(
        *,
        init: Literal[False],
        client_id: ClientId,
        redirect_uri: OAuth2Uri,
        scopes: tuple[PublicScope, ...],
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
        scopes: tuple[PublicScope, ...],
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
        scopes: tuple[PublicScope, ...],
        code_challenge_method: OAuth2CodeChallengeMethod | None,
        code_challenge: str | None,
        state: str | None,
    ) -> dict[str, str] | OAuth2TokenOOB | OAuth2Application:
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

        app = await OAuth2ApplicationQuery.find_one_by_client_id(client_id)
        if app is None or oauth2_app_is_system(app):
            raise_for.oauth_bad_client_id()

        if redirect_uri not in app['redirect_uris']:
            raise_for.oauth_bad_redirect_uri()

        scopes_set = set(scopes)
        if not scopes_set.issubset(app['scopes']):
            raise_for.oauth_bad_scopes()

        if init:
            tokens = await OAuth2TokenQuery.find_many_authorized_by_user_app_id(
                user_id=user_id,
                app_id=app['id'],
                limit=OAUTH_SILENT_AUTH_QUERY_SESSION_LIMIT,
            )

            for token in tokens:
                # Ignore different redirect URI
                if token['redirect_uri'] != redirect_uri:
                    continue
                # Ignore different scopes
                if scopes_set.symmetric_difference(token['scopes']):
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
            'name': None,
            'token_hashed': authorization_code_hashed,
            'token_preview': None,
            'redirect_uri': redirect_uri,
            'scopes': list(scopes),
            'code_challenge_method': code_challenge_method,
            'code_challenge': code_challenge,
        }

        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO oauth2_token (
                    id, user_id, application_id, name,
                    token_hashed, token_preview, redirect_uri,
                    scopes, code_challenge_method, code_challenge
                )
                VALUES (
                    %(id)s, %(user_id)s, %(application_id)s, %(name)s,
                    %(token_hashed)s, %(token_preview)s, %(redirect_uri)s,
                    %(scopes)s, %(code_challenge_method)s, %(code_challenge)s
                )
                """,
                token_init,
            )

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
    ) -> dict[str, str | int]:
        """
        Exchange an authorization code for an access token.
        The access token can be used to make requests on behalf of the user.
        """
        app = await OAuth2ApplicationQuery.find_one_by_client_id(client_id)
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
            async with await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM oauth2_token
                WHERE token_hashed = %s
                AND created_at > statement_timestamp() - %s
                AND authorized_at IS NULL
                FOR UPDATE
                """,
                (authorization_code_hashed, OAUTH_AUTHORIZATION_CODE_TIMEOUT),
            ) as r:
                token: OAuth2Token | None = await r.fetchone()  # type: ignore
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
                    raise NotImplementedError(  # noqa: TRY301
                        f'Unsupported OAuth2 code challenge method {token["code_challenge_method"]!r}'
                    )

            except Exception:
                # Delete the token if verification fails
                await conn.execute(
                    """
                    DELETE FROM oauth2_token
                    WHERE id = %s
                    """,
                    (token['id'],),
                )
                raise

            access_token = buffered_rand_urlsafe(32)
            access_token_hashed = hash_bytes(access_token)

            async with await conn.execute(
                """
                UPDATE oauth2_token
                SET token_hashed = %s,
                    authorized_at = statement_timestamp(),
                    redirect_uri = NULL,
                    code_challenge_method = NULL,
                    code_challenge = NULL
                WHERE id = %s
                RETURNING authorized_at
                """,
                (access_token_hashed, token['id']),
            ) as r:
                authorized_at: datetime = (await r.fetchone())[0]  # type: ignore

        return {
            'access_token': access_token,
            'token_type': 'Bearer',
            'scope': ' '.join(token['scopes']),
            'created_at': int(authorized_at.timestamp()),
            # TODO: id_token
        }

    @staticmethod
    async def create_pat(
        *, name: str, scopes: tuple[PublicScope, ...]
    ) -> OAuth2TokenId:
        """Create a new Personal Access Token with the given name and scopes. Returns the token id."""
        app_id = SYSTEM_APP_CLIENT_ID_MAP[SYSTEM_APP_PAT_CLIENT_ID]
        user_id = auth_user(required=True)['id']

        token_id: OAuth2TokenId = zid()  # type: ignore
        token_init: OAuth2TokenInit = {
            'id': token_id,
            'user_id': user_id,
            'application_id': app_id,
            'name': name,
            'token_hashed': None,
            'token_preview': None,
            'redirect_uri': None,
            'scopes': list(scopes),
            'code_challenge_method': None,
            'code_challenge': None,
        }

        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO oauth2_token (
                    id, user_id, application_id, name,
                    token_hashed, token_preview, redirect_uri,
                    scopes, code_challenge_method, code_challenge
                )
                VALUES (
                    %(id)s, %(user_id)s, %(application_id)s, %(name)s,
                    %(token_hashed)s, %(token_preview)s, %(redirect_uri)s,
                    %(scopes)s, %(code_challenge_method)s, %(code_challenge)s
                )
                """,
                token_init,
            )

        return token_id

    @staticmethod
    async def reset_pat_access_token(pat_id: OAuth2TokenId) -> SecretStr:
        """Reset the personal access token and return the new secret."""
        app_id = SYSTEM_APP_CLIENT_ID_MAP[SYSTEM_APP_PAT_CLIENT_ID]
        access_token_ = buffered_rand_urlsafe(32)
        access_token_hashed = hash_bytes(access_token_)
        access_token_preview = access_token_[:OAUTH_SECRET_PREVIEW_LENGTH]
        access_token = SecretStr(access_token_)
        del access_token_
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await conn.execute(
                """
                UPDATE oauth2_token
                SET token_hashed = %s,
                    token_preview = %s,
                    authorized_at = statement_timestamp()
                WHERE id = %s
                AND user_id = %s
                AND application_id = %s
                """,
                (
                    access_token_hashed,
                    access_token_preview,
                    pat_id,
                    user_id,
                    app_id,
                ),
            )

        return access_token

    @staticmethod
    async def revoke_by_id(token_id: OAuth2TokenId) -> None:
        """Revoke the given token by id."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await conn.execute(
                """
                DELETE FROM oauth2_token
                WHERE id = %s AND user_id = %s
                """,
                (token_id, user_id),
            )

        logging.debug('Revoked OAuth2 token %d', token_id)

    @staticmethod
    async def revoke_by_access_token(access_token: SecretStr) -> None:
        """Revoke the given access token."""
        access_token_hashed = hash_bytes(access_token.get_secret_value())

        async with db(True) as conn:
            await conn.execute(
                """
                DELETE FROM oauth2_token
                WHERE token_hashed = %s
                """,
                (access_token_hashed,),
            )

        logging.debug('Revoked OAuth2 access token')

    @staticmethod
    async def revoke_by_app_id(
        app_id: ApplicationId,
        *,
        user_id: UserId | None = None,
        skip_ids: list[OAuth2TokenId] | None = None,
    ) -> None:
        """Revoke all current user tokens for the given OAuth2 application."""
        if user_id is None:
            user_id = auth_user(required=True)['id']

        conditions: list[Composable] = [SQL('user_id = %s AND application_id = %s')]
        params: list[Any] = [user_id, app_id]

        if skip_ids is not None:
            conditions.append(SQL('NOT (id = ANY(%s))'))
            params.append(skip_ids)

        query = SQL("""
            DELETE FROM oauth2_token
            WHERE {conditions}
        """).format(conditions=SQL(' AND ').join(conditions))

        async with db(True) as conn:
            await conn.execute(query, params)

        logging.debug('Revoked OAuth2 app tokens %d for user %d', app_id, user_id)

    @staticmethod
    async def revoke_by_client_id(
        client_id: ClientId,
        *,
        user_id: UserId | None = None,
        skip_ids: list[OAuth2TokenId] | None = None,
    ) -> None:
        """Revoke all current user tokens for the given OAuth2 client."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT id FROM oauth2_application
                WHERE client_id = %s
                """,
                (client_id,),
            ) as r,
        ):
            app: OAuth2Application | None = await r.fetchone()  # type: ignore

        if app is not None:
            await OAuth2TokenService.revoke_by_app_id(
                app['id'], user_id=user_id, skip_ids=skip_ids
            )
