from collections.abc import Sequence

from sqlalchemy import null, select

from app.db import db
from app.lib.crypto import hash_bytes
from app.lib.options_context import apply_options_context
from app.models.db.oauth2_token import OAuth2Token


class OAuth2TokenQuery:
    @staticmethod
    async def find_one_authorized_by_token(token_str: str) -> OAuth2Token | None:
        """
        Find an authorized OAuth2 token by token string.
        """
        token_hashed = hash_bytes(token_str)

        async with db() as session:
            stmt = select(OAuth2Token).where(
                OAuth2Token.token_hashed == token_hashed,
                OAuth2Token.authorized_at != null(),
            )
            stmt = apply_options_context(stmt)
            return await session.scalar(stmt)

    @staticmethod
    async def find_many_authorized_by_user_app(
        user_id: int,
        app_id: int,
        *,
        limit: int | None,
    ) -> Sequence[OAuth2Token]:
        """
        Find all authorized OAuth2 tokens for a user-application pair.
        """
        async with db() as session:
            stmt = (
                select(OAuth2Token)
                .where(
                    OAuth2Token.user_id == user_id,
                    OAuth2Token.application_id == app_id,
                    OAuth2Token.authorized_at != null(),
                )
                .order_by(OAuth2Token.created_at.desc())
            )
            stmt = apply_options_context(stmt)

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()
