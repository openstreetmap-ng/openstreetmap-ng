from psycopg.rows import dict_row

from app.db import db
from app.lib.auth_context import auth_user
from app.models.db.user_pref import UserPref
from app.models.types import ApplicationId, UserPrefKey


class UserPrefQuery:
    @staticmethod
    async def find_by_app_key(
        app_id: ApplicationId | None, key: UserPrefKey
    ) -> UserPref | None:
        """Find a user preference by app id and key."""
        user_id = auth_user(required=True)['id']

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM user_pref
                WHERE user_id = %s
                AND app_id IS NOT DISTINCT FROM %s
                AND key = %s
                """,
                (user_id, app_id, key),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def find_by_app(app_id: ApplicationId | None) -> list[UserPref]:
        """Find all user preferences by app id."""
        user_id = auth_user(required=True)['id']

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM user_pref
                WHERE user_id = %s
                AND app_id IS NOT DISTINCT FROM %s
                """,
                (user_id, app_id),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore
