from psycopg import AsyncConnection

from app.models.types import UserId


class UserTokenService:
    @staticmethod
    async def delete_all_for_user(conn: AsyncConnection, user_id: UserId) -> None:
        """Delete all tokens for the given user."""
        await conn.execute(
            'DELETE FROM user_token WHERE user_id = %s',
            (user_id,),
        )
