from app.db import db
from app.models.db.connected_account import AuthProvider
from app.models.types import UserId


class ConnectedAccountQuery:
    @staticmethod
    async def find_user_id_by_auth_provider(provider: AuthProvider, uid: str) -> UserId | None:
        """Find a user id by auth provider and uid."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT user_id
                FROM connected_account
                WHERE provider = %s AND uid = %s
                """,
                (provider, uid),
            ) as r,
        ):
            row = await r.fetchone()
            return row[0] if row is not None else None

    @staticmethod
    async def get_providers_by_user(user_id: UserId) -> list[AuthProvider]:
        """Get a map of provider ids by user id."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT provider
                FROM connected_account
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            return [c for (c,) in await r.fetchall()]
