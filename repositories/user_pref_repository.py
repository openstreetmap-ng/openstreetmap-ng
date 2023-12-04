from collections.abc import Sequence

from sqlalchemy import select

from db import DB
from lib.auth import auth_user
from models.db.user_pref import UserPref


class UserPrefRepository:
    @staticmethod
    async def find_one_by_app_key(app_id: int | None, key: str) -> UserPref | None:
        """
        Find a user preference by app id and key.
        """

        async with DB() as session:
            stmt = (
                select(UserPref)
                .where(
                    UserPref.user_id == auth_user().id,
                    UserPref.app_id == app_id,
                    UserPref.key == key,
                )
                .limit(1)
            )

            return await session.scalar(stmt)

    @staticmethod
    async def find_many_by_app(app_id: int | None) -> Sequence[UserPref]:
        """
        Find all user preferences by app id.
        """

        async with DB() as session:
            stmt = select(UserPref).where(
                UserPref.user_id == auth_user().id,
                UserPref.app_id == app_id,
            )

            return (await session.scalars(stmt)).all()
