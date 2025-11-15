from typing import Any

import cython
from psycopg.sql import SQL, Composable

from app.config import USER_PREF_BULK_SET_LIMIT
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.models.db.user_pref import UserPref
from app.models.types import ApplicationId, UserPrefKey
from app.services.audit_service import audit

# TODO: make it clear not to store sensitive data or to encrypt it
# TODO: limit app prefs count
# TODO: limit gpx count, cleanup raw files?
# TODO: 0.7 struct, 1 entry per app


class UserPrefService:
    @staticmethod
    async def upsert(prefs: list[UserPref]) -> None:
        """Set user preferences."""
        num_prefs: cython.size_t = len(prefs)
        if not num_prefs:
            return
        if num_prefs > USER_PREF_BULK_SET_LIMIT:
            raise_for.pref_bulk_set_limit_exceeded()

        values: list[Composable] = [SQL('(%s, %s, %s, %s)')] * num_prefs
        params: list[Any] = []
        for pref in prefs:
            params.extend((pref['user_id'], pref['app_id'], pref['key'], pref['value']))

        query = SQL("""
            INSERT INTO user_pref (
                user_id, app_id, key, value
            )
            VALUES {}
            ON CONFLICT (user_id, app_id, key) DO UPDATE SET
                value = EXCLUDED.value
        """).format(SQL(',').join(values))

        async with db(True) as conn:
            await conn.execute(query, params)
            await audit(
                'update_prefs',
                conn,
                extra={'prefs': [(pref['app_id'], pref['key']) for pref in prefs]},
            )

    @staticmethod
    async def delete_by_app_key(app_id: ApplicationId | None, key: UserPrefKey) -> None:
        """Delete a user preference by app id and key."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            result = await conn.execute(
                """
                DELETE FROM user_pref
                WHERE user_id = %s
                AND app_id IS NOT DISTINCT FROM %s
                AND key = %s
                """,
                (user_id, app_id, key),
            )
            if result.rowcount:
                await audit('delete_prefs', conn, extra={'app': app_id, 'key': key})

    @staticmethod
    async def delete_by_app(app_id: ApplicationId | None) -> None:
        """Delete all user preferences by app id."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            result = await conn.execute(
                """
                DELETE FROM user_pref
                WHERE user_id = %s
                AND app_id IS NOT DISTINCT FROM %s
                """,
                (user_id, app_id),
            )
            if result.rowcount:
                await audit('delete_prefs', conn, extra={'app': app_id})
