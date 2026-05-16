import logging

from psycopg import AsyncConnection

from app.db import db, db_delete
from app.models.db.user_token import USER_TOKEN_EXPIRE
from app.models.types import UserId


class UserTokenService:
    @staticmethod
    async def delete_all_for_user(conn: AsyncConnection, user_id: UserId):
        """Delete all tokens for the given user."""
        await db_delete('user_token', where={'user_id': user_id}, conn=conn)

    @staticmethod
    async def delete_expired():
        """Delete all expired tokens of all types."""
        async with db(True, autocommit=True) as conn:
            total = 0
            for token_type, expire in USER_TOKEN_EXPIRE.items():
                total += await db_delete(
                    'user_token',
                    where=t'type = {token_type} AND created_at <= statement_timestamp() - {expire}',
                    conn=conn,
                )
            if total:
                logging.debug('Deleted %d expired user tokens', total)
