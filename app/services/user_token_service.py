import logging

from psycopg import AsyncConnection

from app.db import db
from app.models.db.user_token import USER_TOKEN_EXPIRE
from app.models.types import UserId


class UserTokenService:
    @staticmethod
    async def delete_all_for_user(conn: AsyncConnection, user_id: UserId):
        """Delete all tokens for the given user."""
        await conn.execute(
            'DELETE FROM user_token WHERE user_id = %s',
            (user_id,),
        )

    @staticmethod
    async def delete_expired():
        """Delete all expired tokens of all types."""
        async with db(True, autocommit=True) as conn:
            total = 0
            for token_type, expire in USER_TOKEN_EXPIRE.items():
                result = await conn.execute(
                    """
                    DELETE FROM user_token
                    WHERE type = %s
                      AND created_at <= statement_timestamp() - %s
                    """,
                    (token_type, expire),
                )
                total += result.rowcount
            if total:
                logging.debug('Deleted %d expired user tokens', total)
