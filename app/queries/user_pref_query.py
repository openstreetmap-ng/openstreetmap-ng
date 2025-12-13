from psycopg.rows import dict_row

from app.db import db
from app.lib.auth_context import auth_user
from app.models.db.user_pref import UserPref
from app.models.types import ApplicationId, UserPrefKey


class UserPrefQuery:
    @staticmethod
    async def find(
        app_id: ApplicationId | None, *, key: UserPrefKey | None = None
    ) -> list[UserPref]:
        """Find user preferences by app id and optional key."""
        user_id = auth_user(required=True)['id']

        if key is not None:
            query = """
                SELECT * FROM user_pref
                WHERE user_id = %s
                AND app_id IS NOT DISTINCT FROM %s
                AND key = %s
            """
            params = (user_id, app_id, key)
        else:
            query = """
                SELECT * FROM user_pref
                WHERE user_id = %s
                AND app_id IS NOT DISTINCT FROM %s
            """
            params = (user_id, app_id)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore
