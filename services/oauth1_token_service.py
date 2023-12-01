import secrets
from collections.abc import Sequence
from urllib.parse import urlencode

from sqlalchemy import func, null, select
from sqlalchemy.orm import joinedload

from db import DB
from lib.crypto import hash_b
from lib.exceptions import raise_for
from models.db.oauth1_token import OAuth1Token
from models.scope import Scope
from repositories.oauth1_application_repository import OAuth1ApplicationRepository
from utils import extend_query_params


class OAuth1TokenService:
    @staticmethod
    async def request_token(consumer_key: str, callback_url: str | None) -> dict:
        """
        Create a new request token.

        At this stage, the token only references the application.
        """

        app = await OAuth1ApplicationRepository.find_by_consumer_key(consumer_key)

        if not app:
            raise_for().oauth_bad_app_token()

        token_str = secrets.token_urlsafe(32)
        token_hashed = hash_b(token_str, context=None)
        token_secret = secrets.token_urlsafe(32)

        async with DB() as session:
            session.add(
                OAuth1Token(
                    user_id=None,
                    application_id=app.id,
                    token_hashed=token_hashed,
                    token_secret=token_secret,
                    scopes=[],
                    callback_url=callback_url,
                    verifier=None,
                )
            )

        result = {
            'oauth_token': token_str,
            'oauth_token_secret': token_secret,
        }

        if callback_url:
            result['oauth_callback_confirmed'] = 'true'

        return result

    @staticmethod
    async def authorize(token_str: str, user_id: int, scopes: Sequence[Scope]) -> str:
        """
        Authorize a request token for a user.

        The token is updated to reference the user and the given scopes.

        The verifier is returned to the client and must be used
        to exchange the request token for a valid access token.
        """

        token_hashed = hash_b(token_str, context=None)

        async with DB() as session, session.begin():
            stmt = (
                select(OAuth1Token)
                .options(joinedload(OAuth1Token.application))
                .where(
                    OAuth1Token.token_hashed == token_hashed,
                    OAuth1Token.user_id == null(),
                )
                .with_for_update()
            )

            token = await session.scalar(stmt)

            if not token:
                raise_for().oauth_bad_user_token()
            if not set(scopes).issubset(token.application.scopes):
                raise_for().oauth_bad_scopes()

            verifier = secrets.token_urlsafe(32)

            token.user_id = user_id
            token.scopes = scopes
            token.verifier = verifier

        params = {
            'oauth_token': token,
            'oauth_verifier': verifier,
        }

        if token.callback_url:
            return extend_query_params(token.callback_url, params)
        else:
            return urlencode(params)

    @staticmethod
    async def access_token(token_str: str, verifier: str) -> dict:
        """
        Exchange a request token for an access token.

        The access token can be used to make requests on behalf of the user.
        """

        token_hashed = hash_b(token_str, context=None)

        async with DB() as session, session.begin():
            stmt = (
                select(OAuth1Token)
                .options(joinedload(OAuth1Token.application))
                .where(
                    OAuth1Token.token_hashed == token_hashed,
                    OAuth1Token.user_id != null(),
                    OAuth1Token.authorized_at == null(),
                )
                .with_for_update()
            )

            token = await session.scalar(stmt)

            if not token:
                raise_for().oauth_bad_user_token()

            try:
                if token.verifier != verifier:
                    raise_for().oauth1_bad_verifier()
            except Exception:
                # delete the token if the verification fails
                await session.delete(token)
                raise

            token_str = secrets.token_urlsafe(32)
            token_hashed = hash_b(token_str, context=None)
            token_secret = secrets.token_urlsafe(32)

            token.token_hashed = token_hashed
            token.key_secret = token_secret
            token.authorized_at = func.now()
            token.verifier = None

        return {
            'oauth_token': token_str,
            'oauth_token_secret': token_secret,
        }
