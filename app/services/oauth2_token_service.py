from collections.abc import Iterable
from hmac import compare_digest

from pydantic import SecretStr
from sqlalchemy import delete, func, null, select, update
from sqlalchemy.orm import joinedload

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_rand_urlsafe
from app.lib.crypto import hash_bytes, hash_s256_code_challenge
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.options_context import options_context
from app.limits import (
    OAUTH_AUTHORIZATION_CODE_TIMEOUT,
    OAUTH_SECRET_PREVIEW_LENGTH,
    OAUTH_SILENT_AUTH_QUERY_SESSION_LIMIT,
)
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.oauth2_token import OAuth2CodeChallengeMethod, OAuth2Token, OAuth2TokenOOB
from app.models.db.user import User
from app.models.scope import Scope
from app.models.types import Uri
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.services.system_app_service import SYSTEM_APP_CLIENT_ID_MAP

# TODO: limit number of access tokens per user+app


class OAuth2TokenService:
    @staticmethod
    async def authorize(
        *,
        init: bool,
        client_id: str,
        redirect_uri: str,
        scopes: tuple[Scope, ...],
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
            raise_for().oauth2_bad_code_challenge_params()

        with options_context(
            joinedload(OAuth2Application.user).load_only(
                User.id,
                User.display_name,
                User.avatar_type,
                User.avatar_id,
            )
        ):
            app = await OAuth2ApplicationQuery.find_one_by_client_id(client_id)
        if app is None or app.is_system_app:
            raise_for().oauth_bad_client_id()
        if redirect_uri not in app.redirect_uris:
            raise_for().oauth_bad_redirect_uri()
        redirect_uri = Uri(redirect_uri)  # mark as valid

        user_id = auth_user(required=True).id
        scopes_set = set(scopes)
        if not scopes_set.issubset(app.scopes):
            raise_for().oauth_bad_scopes()

        # handle silent authentication
        if init:
            tokens = await OAuth2TokenQuery.find_many_authorized_by_user_app_id(
                user_id=user_id,
                app_id=app.id,
                limit=OAUTH_SILENT_AUTH_QUERY_SESSION_LIMIT,
            )
            for token in tokens:
                # ignore different redirect uri
                if token.redirect_uri != redirect_uri:
                    continue
                # ignore different scopes
                if scopes_set.symmetric_difference(token.scopes):
                    continue
                # session found, auto-approve
                break
            else:
                # no session found, require manual approval
                return app

        authorization_code = buffered_rand_urlsafe(32)
        authorization_code_hashed = hash_bytes(authorization_code)

        async with db_commit() as session:
            token = OAuth2Token(
                user_id=user_id,
                application_id=app.id,
                token_hashed=authorization_code_hashed,
                scopes=scopes,
                redirect_uri=redirect_uri,
                code_challenge_method=code_challenge_method,
                code_challenge=code_challenge,
            )
            session.add(token)

        if token.is_oob:
            return OAuth2TokenOOB(authorization_code, state)

        params = {'code': authorization_code}
        if state is not None:
            params['state'] = state
        return params

    @staticmethod
    async def token(
        *,
        client_id: str,
        client_secret: SecretStr | None,
        authorization_code: str,
        verifier: str | None,
        redirect_uri: str,
    ) -> dict[str, str | int]:
        """
        Exchange an authorization code for an access token.

        The access token can be used to make requests on behalf of the user.
        """
        app = await OAuth2ApplicationQuery.find_one_by_client_id(client_id)
        if app is None or app.is_system_app:
            raise_for().oauth_bad_client_id()
        if app.is_confidential and (
            client_secret is None
            or app.client_secret_hashed is None
            or not compare_digest(app.client_secret_hashed, hash_bytes(client_secret.get_secret_value()))
        ):
            raise_for().oauth_bad_client_secret()

        authorization_code_hashed = hash_bytes(authorization_code)
        async with db_commit() as session:
            stmt = (
                select(OAuth2Token)
                .where(
                    OAuth2Token.token_hashed == authorization_code_hashed,
                    OAuth2Token.created_at > utcnow() - OAUTH_AUTHORIZATION_CODE_TIMEOUT,
                    OAuth2Token.authorized_at == null(),
                )
                .with_for_update()
            )
            token = await session.scalar(stmt)
            if token is None:
                raise_for().oauth_bad_user_token()

            try:
                # verify redirect_uri
                if token.redirect_uri != redirect_uri:
                    raise_for().oauth_bad_redirect_uri()

                # verify code_challenge
                if token.code_challenge_method is None:
                    if verifier is not None:
                        raise_for().oauth2_challenge_method_not_set()
                elif token.code_challenge_method == OAuth2CodeChallengeMethod.plain:
                    if token.code_challenge != verifier:
                        raise_for().oauth2_bad_verifier(token.code_challenge_method)
                elif token.code_challenge_method == OAuth2CodeChallengeMethod.S256:
                    if verifier is None or token.code_challenge != hash_s256_code_challenge(verifier):
                        raise_for().oauth2_bad_verifier(token.code_challenge_method)
                else:
                    raise NotImplementedError(  # noqa: TRY301
                        f'Unsupported OAuth2 code challenge method {token.code_challenge_method!r}'
                    )
            except Exception:
                # delete the token if the verification fails
                await session.delete(token)
                raise

            access_token = buffered_rand_urlsafe(32)
            access_token_hashed = hash_bytes(access_token)

            token.token_hashed = access_token_hashed
            token.authorized_at = utcnow()
            token.redirect_uri = None
            token.code_challenge_method = None
            token.code_challenge = None

        return {
            'access_token': access_token,
            'token_type': 'Bearer',
            'scope': token.scopes_str,
            'created_at': int(token.authorized_at.timestamp()),
            # TODO: id_token
        }

    @staticmethod
    async def create_pat(*, name: str, scopes: tuple[Scope, ...]) -> int:
        """
        Create a new Personal Access Token with the given name and scopes.

        Returns the token id.
        """
        app_id = SYSTEM_APP_CLIENT_ID_MAP['SystemApp.pat']
        async with db_commit() as session:
            token = OAuth2Token(
                user_id=auth_user(required=True).id,
                application_id=app_id,
                token_hashed=None,
                scopes=scopes,
                redirect_uri=None,
                code_challenge_method=None,
                code_challenge=None,
            )
            token.name = name
            session.add(token)
        return token.id

    @staticmethod
    async def reset_pat_acess_token(pat_id: int) -> SecretStr:
        """
        Reset the personal access token and return the new secret.
        """
        app_id = SYSTEM_APP_CLIENT_ID_MAP['SystemApp.pat']
        access_token = buffered_rand_urlsafe(32)
        access_token_hashed = hash_bytes(access_token)
        async with db_commit() as session:
            stmt = (
                update(OAuth2Token)
                .where(
                    OAuth2Token.id == pat_id,
                    OAuth2Token.user_id == auth_user(required=True).id,
                    OAuth2Token.application_id == app_id,
                )
                .values(
                    {
                        OAuth2Token.token_hashed: access_token_hashed,
                        OAuth2Token.token_preview: access_token[:OAUTH_SECRET_PREVIEW_LENGTH],
                        OAuth2Token.authorized_at: func.statement_timestamp(),
                    }
                )
                .inline()
            )
            await session.execute(stmt)
        return SecretStr(access_token)

    @staticmethod
    async def revoke_by_id(token_id: int) -> None:
        """
        Revoke the given token by id.
        """
        async with db_commit() as session:
            stmt = delete(OAuth2Token).where(
                OAuth2Token.user_id == auth_user(required=True).id,
                OAuth2Token.id == token_id,
            )
            await session.execute(stmt)

    @staticmethod
    async def revoke_by_access_token(access_token: SecretStr) -> None:
        """
        Revoke the given access token.
        """
        access_token_hashed = hash_bytes(access_token.get_secret_value())
        async with db_commit() as session:
            stmt = delete(OAuth2Token).where(OAuth2Token.token_hashed == access_token_hashed)
            await session.execute(stmt)

    @staticmethod
    async def revoke_by_app_id(app_id: int, *, skip_ids: Iterable[int] | None = None) -> None:
        """
        Revoke all current user tokens for the given OAuth2 application.
        """
        if skip_ids is None:
            skip_ids = ()
        async with db_commit() as session:
            stmt = delete(OAuth2Token).where(
                OAuth2Token.user_id == auth_user(required=True).id,
                OAuth2Token.application_id == app_id,
                OAuth2Token.id.notin_(skip_ids),
            )
            await session.execute(stmt)

    @staticmethod
    async def revoke_by_client_id(client_id: str, *, skip_ids: Iterable[int] | None = None) -> None:
        """
        Revoke all current user tokens for the given OAuth2 client.
        """
        app = await OAuth2ApplicationQuery.find_one_by_client_id(client_id)
        if app is None:
            return
        await OAuth2TokenService.revoke_by_app_id(app.id, skip_ids=skip_ids)
