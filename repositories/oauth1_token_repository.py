from sqlalchemy import null, select
from sqlalchemy.orm import joinedload

from db import DB
from lib.crypto import hash_b
from models.db.oauth1_token import OAuth1Token


class OAuth1TokenRepository:
    @staticmethod
    async def find_one_by_token(token_str: str) -> OAuth1Token | None:
        """
        Find an OAuth1 token by token string.
        """

        token_hashed = hash_b(token_str, context=None)

        # TODO: always joinedload
        async with DB() as session:
            stmt = (
                select(OAuth1Token)
                .options(joinedload(OAuth1Token.application, OAuth1Token.user))
                .where(OAuth1Token.token_hashed == token_hashed)
            )

            return await session.scalar(stmt)
