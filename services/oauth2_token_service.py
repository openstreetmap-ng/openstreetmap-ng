import secrets
from collections.abc import Sequence

from sqlalchemy import null, select
from sqlalchemy.orm import joinedload

from db import DB
from lib.crypto import hash_b
from lib.exceptions import raise_for
from models.db.oauth2_token import OAuth2Token
from models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod
from models.scope import Scope
from repositories.oauth2_application_repository import OAuth2ApplicationRepository
from utils import extend_query_params, utcnow


class OAuth2TokenService:
    @staticmethod
    async def authorize(
        user_id: int,
        client_id: str,
        redirect_uri: str,
        scopes: Sequence[Scope],
        code_challenge: str | None,
        code_challenge_method: OAuth2CodeChallengeMethod | None,
        state: str | None,
    ) -> str:
        """
        Create a new authorization code.

        The code can be exchanged for an access token.

        Returns the redirect uri with the authorization code as a query parameter.
        """

        app = await OAuth2ApplicationRepository.find_by_client_id(client_id)

        if not app:
            raise_for().oauth_bad_app_token()
        if redirect_uri not in app.redirect_uris:
            raise_for().oauth_bad_redirect_uri()
        if not set(scopes).issubset(app.scopes):
            raise_for().oauth_bad_scopes()

        authorization_code = secrets.token_urlsafe(32)
        authorization_code_hashed = hash_b(authorization_code, context=None)

        async with DB() as session:
            session.add(
                OAuth2Token(
                    user_id=user_id,
                    application_id=app.id,
                    token_hashed=authorization_code_hashed,
                    scopes=scopes,
                    redirect_uri=redirect_uri,
                    code_challenge=code_challenge,
                    code_challenge_method=code_challenge_method,
                )
            )

        params = {
            'code': authorization_code,
        }

        if state:
            params['state'] = state

        # TODO: support OOB
        return extend_query_params(redirect_uri, params)

    @staticmethod
    async def token(authorization_code: str, verifier: str | None) -> dict:
        """
        Exchange an authorization code for an access token.

        The access token can be used to make requests on behalf of the user.
        """

        authorization_code_hashed = hash_b(authorization_code, context=None)

        async with DB() as session, session.begin():
            stmt = (
                select(OAuth2Token)
                .options(joinedload(OAuth2Token.application))
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
            access_token_hashed = hash_b(access_token, context=None)

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
