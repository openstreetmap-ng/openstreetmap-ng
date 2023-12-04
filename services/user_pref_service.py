import logging

from sqlalchemy import delete

from db import DB
from lib.auth import auth_user
from models.db.user_pref import UserPref

# TODO: make it clear not to store sensitive data or to encrypt it
# TODO: limit app prefs count
# TOOD: limit gpx count, cleanup raw files?


class UserPrefService:
    @staticmethod
    async def set_by_app_key(app_id: int | None, key: str, value: str | None) -> None:
        """
        Set a user preference by app id and key.

        If value is None, the preference will be deleted.
        """

        async with DB() as session:
            if value:
                logging.debug('Setting user pref %r', key)
                session.add(
                    UserPref(
                        user_id=auth_user().id,
                        app_id=app_id,
                        key=key,
                        value=value,
                    )
                )
            else:
                logging.debug('Deleting user pref %r', key)
                stmt = delete(UserPref).where(
                    UserPref.user_id == auth_user().id,
                    UserPref.app_id == app_id,
                    UserPref.key == key,
                )

                await session.execute(stmt)
