from app.db import db_fetchall
from app.lib.auth.context import auth_user
from app.models.db.user_pref import UserPref
from app.models.types import ApplicationId, UserPrefKey


class UserPrefQuery:
    @staticmethod
    async def find(
        app_id: ApplicationId | None, *, key: UserPrefKey | None = None
    ) -> list[UserPref]:
        """Find user preferences by app id and optional key."""
        user_id = auth_user(required=True)['id']

        key_filter = t'AND key = {key}' if key is not None else t''

        return await db_fetchall(
            UserPref,
            t"""
                SELECT * FROM user_pref
                WHERE user_id = {user_id}
                AND app_id IS NOT DISTINCT FROM {app_id}
                {key_filter:q}
            """,
        )
