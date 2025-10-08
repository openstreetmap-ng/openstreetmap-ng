from psycopg.rows import dict_row

from app.db import db
from app.lib.auth_context import auth_user
from app.models.db.connected_account import AuthProvider, ConnectedAccount
from app.models.types import UserId


class ConnectedAccountQuery:
    @staticmethod
    async def find_user_id_by_auth_provider(
        provider: AuthProvider, uid: str
    ) -> UserId | None:
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
    async def find_by_user(user_id: UserId | None = None) -> list[ConnectedAccount]:
        """Get all connected accounts for a user."""
        if user_id is None:
            user_id = auth_user(required=True)['id']

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT *
                FROM connected_account
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore
