from sqlalchemy import select
from sqlalchemy.orm import joinedload

from db import DB
from lib.crypto import hash_b
from models.db.oauth2_token import OAuth2Token


class OAuth2TokenRepository:
    @staticmethod
    async def find_one_by_token(token_str: str) -> OAuth2Token | None:
        """
        Find an OAuth2 token by token string.
        """

        token_hashed = hash_b(token_str, context=None)

        async with DB() as session:
            stmt = (
                select(OAuth2Token)
                .options(joinedload(OAuth2Token.application))
                .where(OAuth2Token.token_hashed == token_hashed)
            )

            return await session.scalar(stmt)
