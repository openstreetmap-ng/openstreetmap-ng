import cython

from app.config import USER_PREF_BULK_SET_LIMIT
from app.db import db, db_delete, db_insert_many
from app.exceptions.context import raise_for
from app.lib.audit import audit
from app.lib.auth.context import auth_user
from app.models.db.user_pref import UserPref
from app.models.types import ApplicationId, UserPrefKey

# TODO: make it clear not to store sensitive data or to encrypt it
# TODO: limit app prefs count
# TODO: limit gpx count, cleanup raw files?
# TODO: 0.7 struct, 1 entry per app


class UserPrefService:
    @staticmethod
    async def upsert(prefs: list[UserPref]):
        """Set user preferences."""
        num_prefs: cython.size_t = len(prefs)
        if num_prefs == 0:
            return
        if num_prefs > USER_PREF_BULK_SET_LIMIT:
            raise_for.pref_bulk_set_limit_exceeded()

        async with db(True) as conn:
            await db_insert_many(
                'user_pref',
                [
                    {
                        'user_id': pref['user_id'],
                        'app_id': pref['app_id'],
                        'key': pref['key'],
                        'value': pref['value'],
                    }
                    for pref in prefs
                ],
                on_conflict=t'(user_id, app_id, key) DO UPDATE SET value = EXCLUDED.value',
                conn=conn,
            )
            await audit(
                'update_prefs',
                conn,
                extra={'prefs': [(pref['app_id'], pref['key']) for pref in prefs]},
            )

    @staticmethod
    async def delete(app_id: ApplicationId | None, *, key: UserPrefKey | None = None):
        """Delete user preference(s) by app id and optional key."""
        user_id = auth_user(required=True)['id']
        key_filter = t'AND key = {key}' if key is not None else t''

        async with db(True) as conn:
            rowcount = await db_delete(
                'user_pref',
                where=t"""user_id = {user_id}
                    AND app_id IS NOT DISTINCT FROM {app_id}
                    {key_filter:q}""",
                conn=conn,
            )
            if rowcount:
                await audit('delete_prefs', conn, extra={'app': app_id, 'key': key})
