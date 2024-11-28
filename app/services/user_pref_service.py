import logging
from collections.abc import Collection

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.limits import USER_PREF_BULK_SET_LIMIT
from app.models.db.user_pref import UserPref

# TODO: make it clear not to store sensitive data or to encrypt it
# TODO: limit app prefs count
# TODO: limit gpx count, cleanup raw files?
# TODO: 0.7 struct, 1 entry per app


class UserPrefService:
    @staticmethod
    async def upsert_one(pref: UserPref) -> None:
        """
        Set a user preference.
        """
        async with db_commit() as session:
            logging.debug('Setting user pref %r for app %r', pref.key, pref.app_id)
            stmt = (
                insert(UserPref)
                .values(
                    {
                        UserPref.user_id: pref.user_id,
                        UserPref.app_id: pref.app_id,
                        UserPref.key: pref.key,
                        UserPref.value: pref.value,
                    }
                )
                .on_conflict_do_update(
                    index_elements=(UserPref.user_id, UserPref.app_id, UserPref.key),
                    set_={UserPref.value: pref.value},
                )
                .inline()
            )
            await session.execute(stmt)

    @staticmethod
    async def upsert_many(prefs: Collection[UserPref]) -> None:
        """
        Set multiple user preferences.
        """
        if len(prefs) > USER_PREF_BULK_SET_LIMIT:
            raise_for.pref_bulk_set_limit_exceeded()

        async with db_commit() as session:
            for pref in prefs:
                logging.debug('Setting user pref %r for app %r', pref.key, pref.app_id)

            stmt = (
                insert(UserPref)
                .values(
                    tuple(
                        {
                            UserPref.user_id: pref.user_id,
                            UserPref.app_id: pref.app_id,
                            UserPref.key: pref.key,
                            UserPref.value: pref.value,
                        }
                        for pref in prefs
                    )
                )
                .on_conflict_do_update(
                    index_elements=(UserPref.user_id, UserPref.app_id, UserPref.key),
                    set_={UserPref.value: UserPref.value},
                )
                .inline()
            )
            await session.execute(stmt)

    @staticmethod
    async def delete_by_app_key(app_id: int | None, key: str) -> None:
        """
        Delete a user preference by app id and key.
        """
        async with db_commit() as session:
            logging.debug('Deleting user pref %r for app %r', key, app_id)
            stmt = delete(UserPref).where(
                UserPref.user_id == auth_user(required=True).id,
                UserPref.app_id == app_id,
                UserPref.key == key,
            )
            await session.execute(stmt)

    @staticmethod
    async def delete_by_app(app_id: int | None) -> None:
        """
        Delete all user preferences by app id.
        """
        async with db_commit() as session:
            logging.debug('Deleting user prefs for app %r', app_id)
            stmt = delete(UserPref).where(
                UserPref.user_id == auth_user(required=True).id,
                UserPref.app_id == app_id,
            )
            await session.execute(stmt)
