import logging
from typing import Any

import cython
from psycopg.sql import SQL, Composable

from app.db import db2
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.limits import USER_PREF_BULK_SET_LIMIT
from app.models.db.oauth2_application import ApplicationId
from app.models.db.user_pref import UserPref, UserPrefKey

# TODO: make it clear not to store sensitive data or to encrypt it
# TODO: limit app prefs count
# TODO: limit gpx count, cleanup raw files?
# TODO: 0.7 struct, 1 entry per app


class UserPrefService:
    @staticmethod
    async def upsert(prefs: list[UserPref]) -> None:
        """Set user preferences."""
        num_prefs: cython.Py_ssize_t = len(prefs)
        if not num_prefs:
            return
        if num_prefs > USER_PREF_BULK_SET_LIMIT:
            raise_for.pref_bulk_set_limit_exceeded()

        values: list[Composable] = [SQL('(%s, %s, %s, %s)')] * num_prefs
        params: list[Any] = []
        for pref in prefs:
            logging.debug('Setting user pref %r for app %r', pref['key'], pref['app_id'])
            params.extend((pref['user_id'], pref['app_id'], pref['key'], pref['value']))

        query = SQL("""
            INSERT INTO user_pref (
                user_id, app_id, key, value
            )
            VALUES {}
            ON CONFLICT (user_id, app_id, key) DO UPDATE
            SET value = EXCLUDED.value
        """).format(SQL(',').join(values))

        async with db2(True) as conn:
            await conn.execute(query, params)

    @staticmethod
    async def delete_by_app_key(app_id: ApplicationId | None, key: UserPrefKey) -> None:
        """Delete a user preference by app id and key."""
        user_id = auth_user(required=True)['id']

        async with db2(True) as conn:
            logging.debug('Deleting user pref %r for app %r', key, app_id)
            await conn.execute(
                """
                DELETE FROM user_pref
                WHERE user_id = %s
                AND app_id IS NOT DISTINCT FROM %s
                AND key = %s
                """,
                (user_id, app_id, key),
            )

    @staticmethod
    async def delete_by_app(app_id: ApplicationId | None) -> None:
        """Delete all user preferences by app id."""
        user_id = auth_user(required=True)['id']

        async with db2(True) as conn:
            logging.debug('Deleting user prefs for app %r', app_id)
            await conn.execute(
                """
                DELETE FROM user_pref
                WHERE user_id = %s
                AND app_id IS NOT DISTINCT FROM %s
                """,
                (user_id, app_id),
            )
