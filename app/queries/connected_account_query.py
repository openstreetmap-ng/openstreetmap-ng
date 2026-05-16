from app.db import db_fetchall, db_fetchval
from app.lib.auth.context import auth_user
from app.models.db.connected_account import ConnectedAccount
from app.models.proto.settings_connections_types import Provider
from app.models.types import UserId


class ConnectedAccountQuery:
    @staticmethod
    async def find_user_id_by_auth_provider(
        provider: Provider, uid: str
    ) -> UserId | None:
        """Find a user id by auth provider and uid."""
        return await db_fetchval(
            UserId,
            t"""
                SELECT user_id
                FROM connected_account
                WHERE provider = {provider} AND uid = {uid}
            """,
        )

    @staticmethod
    async def find_by_user(user_id: UserId | None = None) -> list[ConnectedAccount]:
        """Get all connected accounts for a user."""
        if user_id is None:
            user_id = auth_user(required=True)['id']

        return await db_fetchall(
            ConnectedAccount,
            t'SELECT * FROM connected_account WHERE user_id = {user_id}',
        )
