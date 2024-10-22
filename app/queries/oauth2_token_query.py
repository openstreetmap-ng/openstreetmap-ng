from collections.abc import Sequence

from sqlalchemy import func, null, select

from app.db import db
from app.lib.crypto import hash_bytes
from app.lib.options_context import apply_options_context
from app.models.db.oauth2_token import OAuth2Token
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.services.system_app_service import SYSTEM_APP_CLIENT_ID_MAP


class OAuth2TokenQuery:
    @staticmethod
    async def find_one_authorized_by_token(access_token: str) -> OAuth2Token | None:
        """
        Find an authorized OAuth2 token by token string.
        """
        access_token_hashed = hash_bytes(access_token)
        async with db() as session:
            stmt = select(OAuth2Token).where(
                OAuth2Token.token_hashed == access_token_hashed,
                OAuth2Token.authorized_at != null(),
            )
            stmt = apply_options_context(stmt)
            return await session.scalar(stmt)

    @staticmethod
    async def find_many_authorized_by_user_app_id(
        user_id: int,
        app_id: int,
        *,
        limit: int | None,
    ) -> Sequence[OAuth2Token]:
        """
        Find all authorized OAuth2 tokens for the given user and app id.
        """
        async with db() as session:
            stmt = (
                select(OAuth2Token)
                .where(
                    OAuth2Token.user_id == user_id,
                    OAuth2Token.application_id == app_id,
                    OAuth2Token.authorized_at != null(),
                )
                .order_by(OAuth2Token.id.desc())
            )
            stmt = apply_options_context(stmt)

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def find_many_authorized_by_user_client_id(
        user_id: int,
        client_id: str,
        *,
        limit: int | None,
    ) -> Sequence[OAuth2Token]:
        """
        Find all authorized tokens for the given user and client id.
        """
        app = await OAuth2ApplicationQuery.find_one_by_client_id(client_id)
        if app is None:
            return ()
        return await OAuth2TokenQuery.find_many_authorized_by_user_app_id(user_id, app.id, limit=limit)

    @staticmethod
    async def find_many_pats_by_user(
        user_id: int,
        *,
        limit: int | None,
    ) -> Sequence[OAuth2Token]:
        """
        Find all PAT tokens (authorized or not) for the given user.
        """
        app_id = SYSTEM_APP_CLIENT_ID_MAP['SystemApp.pat']
        async with db() as session:
            stmt = (
                select(OAuth2Token)
                .where(
                    OAuth2Token.user_id == user_id,
                    OAuth2Token.application_id == app_id,
                )
                .order_by(OAuth2Token.id.desc())
            )
            stmt = apply_options_context(stmt)

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def find_unique_per_app_by_user_id(user_id: int) -> Sequence[OAuth2Token]:
        """
        Find unique OAuth2 tokens per app for the given user.
        """
        async with db() as session:
            subq = (
                select(func.max(OAuth2Token.id))
                .where(
                    OAuth2Token.user_id == user_id,
                    OAuth2Token.authorized_at != null(),
                )
                .group_by(OAuth2Token.application_id)
                .subquery()
            )
            stmt = (
                select(OAuth2Token)  #
                .where(OAuth2Token.id.in_(subq.select()))
                .order_by(OAuth2Token.application_id.desc())
            )
            stmt = apply_options_context(stmt)
            return (await session.scalars(stmt)).all()
