import secrets
from collections.abc import Sequence

from sqlalchemy import null, select

from app.db import DB
from app.lib.exceptions import raise_for
from app.lib_cython.auth import auth_user
from app.lib_cython.crypto import hash_bytes
from app.limits import OAUTH2_SILENT_AUTH_QUERY_SESSION_LIMIT
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.oauth2_token import OAuth2Token
from app.models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod
from app.models.scope import Scope
from app.repositories.oauth2_application_repository import OAuth2ApplicationRepository
from app.repositories.oauth2_token_repository import OAuth2TokenRepository
from app.utils import extend_query_params, utcnow


class OAuth2TokenService:
    @staticmethod
    async def authorize(
        *,
        init: bool,
        client_id: str,
        redirect_uri: str,
        scopes: Sequence[Scope],
        code_challenge: str | None,
        code_challenge_method: OAuth2CodeChallengeMethod | None,
        state: str | None,
    ) -> str | OAuth2Application:
        """
        Create a new authorization code.

        The code can be exchanged for an access token.

        In `init=True` mode, silent authentication is performed if the application is already authorized.
        When successful, a redirect url or an authorization code (prefixed with "oob;") is returned.
        Otherwise, the application instance is returned for the user to authorize it.

        In `init=False` mode, a redirect url or an authorization code (prefixed with "oob;") is returned.
        """

        app = await OAuth2ApplicationRepository.find_by_client_id(client_id)

        if not app:
            raise_for().oauth_bad_app_token()
        if redirect_uri not in app.redirect_uris:
            raise_for().oauth_bad_redirect_uri()

        user_id = auth_user().id
        scopes_set = set(scopes)

        if not scopes_set.issubset(app.scopes):
            raise_for().oauth_bad_scopes()

        # handle silent authentication
        if init:
            tokens = await OAuth2TokenRepository.find_many_authorized_by_user_app(
                user_id=user_id,
                app_id=app.id,
                limit=OAUTH2_SILENT_AUTH_QUERY_SESSION_LIMIT,
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

        authorization_code = secrets.token_urlsafe(32)
        authorization_code_hashed = hash_bytes(authorization_code, context=None)

        async with DB() as session:
            token = OAuth2Token(
                user_id=user_id,
                application_id=app.id,
                token_hashed=authorization_code_hashed,
                scopes=scopes,
                redirect_uri=redirect_uri,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
            )

            session.add(token)

        if token.is_oob:
            return f'oob;{authorization_code}'

        params = {
            'code': authorization_code,
        }

        if state:
            params['state'] = state

        return extend_query_params(redirect_uri, params)

    @staticmethod
    async def token(authorization_code: str, verifier: str | None) -> dict:
        """
        Exchange an authorization code for an access token.

        The access token can be used to make requests on behalf of the user.
        """

        authorization_code_hashed = hash_bytes(authorization_code, context=None)

        async with DB() as session, session.begin():
            stmt = (
                select(OAuth2Token)
                .where(
                    OAuth2Token.token_hashed == authorization_code_hashed,
                    OAuth2Token.authorized_at == null(),
                )
                .with_for_update()
            )

            token = await session.scalar(stmt)

            if not token:
                raise_for().oauth_bad_user_token()

            try:
                if token.code_challenge_method is None:
                    if verifier:
                        raise_for().oauth2_challenge_method_not_set()
                elif token.code_challenge_method == OAuth2CodeChallengeMethod.plain:
                    if token.code_challenge != verifier:
                        raise_for().oauth2_bad_verifier(token.code_challenge_method)
                elif token.code_challenge_method == OAuth2CodeChallengeMethod.S256:
                    if token.code_challenge != OAuth2CodeChallengeMethod.compute_s256(verifier):
                        raise_for().oauth2_bad_verifier(token.code_challenge_method)
                else:
                    raise NotImplementedError(
                        f'Unsupported OAuth2 code challenge method {token.code_challenge_method!r}'
                    )
            except Exception:
                # delete the token if the verification fails
                await session.delete(token)
                raise

            access_token = secrets.token_urlsafe(32)
            access_token_hashed = hash_bytes(access_token, context=None)

            token.token_hashed = access_token_hashed
            token.authorized_at = utcnow()
            token.code_challenge = None
            token.code_challenge_method = None

        return {
            'access_token': access_token,
            'token_type': 'Bearer',
            'scope': token.scopes_str,
            'created_at': int(token.authorized_at.timestamp()),
            # TODO: id_token
        }
