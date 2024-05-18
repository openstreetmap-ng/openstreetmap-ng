from sqlalchemy import null, select

from app.db import db
from app.lib.crypto import hash_bytes
from app.lib.options_context import apply_options_context
from app.models.db.oauth1_token import OAuth1Token


class OAuth1TokenQuery:
    @staticmethod
    async def find_one_authorized_by_token(token_str: str) -> OAuth1Token | None:
        """
        Find an authorized OAuth1 token by token string.
        """
        token_hashed = hash_bytes(token_str, context=None)

        async with db() as session:
            stmt = select(OAuth1Token).where(
                OAuth1Token.token_hashed == token_hashed,
                OAuth1Token.authorized_at != null(),
            )
            stmt = apply_options_context(stmt)
            return await session.scalar(stmt)
