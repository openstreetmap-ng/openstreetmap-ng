from collections.abc import Sequence

from shapely import Point
from sqlalchemy import func, null, select

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.options_context import apply_options_context
from app.limits import NEARBY_USERS_RADIUS_METERS
from app.models.db.user import User


class UserRepository:
    @staticmethod
    async def find_one_by_id(user_id: int) -> User | None:
        """
        Find a user by id.
        """
        async with db() as session:
            stmt = select(User).where(User.id == user_id)
            stmt = apply_options_context(stmt)
            return await session.scalar(stmt)

    @staticmethod
    async def find_one_by_display_name(display_name: str) -> User | None:
        """
        Find a user by display name.
        """
        async with db() as session:
            stmt = select(User).where(User.display_name == display_name)
            stmt = apply_options_context(stmt)
            return await session.scalar(stmt)

    @staticmethod
    async def find_one_by_email(email: str) -> User | None:
        """
        Find a user by email.
        """
        async with db() as session:
            stmt = select(User).where(User.email == email)
            stmt = apply_options_context(stmt)
            return await session.scalar(stmt)

    @staticmethod
    async def find_many_by_ids(user_ids: Sequence[int]) -> Sequence[User]:
        """
        Find users by ids.
        """
        async with db() as session:
            stmt = select(User).where(User.id.in_(user_ids))
            stmt = apply_options_context(stmt)
            return (await session.scalars(stmt)).all()

    @staticmethod
    async def find_many_nearby(
        point: Point,
        *,
        max_distance: float = NEARBY_USERS_RADIUS_METERS,
        limit: int | None,
    ) -> Sequence[User]:
        """
        Find nearby users.

        Users position is determined by their home point.
        """
        async with db() as session:
            stmt = (
                select(User)
                .where(
                    User.home_point != null(),
                    func.ST_DWithin(User.home_point, func.ST_GeomFromText(point.wkt, 4326), max_distance),
                )
                .order_by(func.ST_Distance(User.home_point, func.ST_GeomFromText(point.wkt, 4326)))
            )
            stmt = apply_options_context(stmt)

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def check_display_name_available(display_name: str) -> bool:
        """
        Check if a display name is available.
        """
        user = auth_user()
        if user is not None:
            # check if the name is unchanged
            if user.display_name == display_name:
                return True

            # check if the name is available
            other_user = await UserRepository.find_one_by_display_name(display_name)
            return other_user is None or other_user.id == user.id

        else:
            # check if the name is available
            other_user = await UserRepository.find_one_by_display_name(display_name)
            return other_user is None

    @staticmethod
    async def check_email_available(email: str) -> bool:
        """
        Check if an email is available.
        """
        user = auth_user()
        if user is not None:
            # check if the email is unchanged
            if user.email == email:
                return True

            # check if the email is available
            other_user = await UserRepository.find_one_by_email(email)
            return other_user is None or other_user.id == user.id

        else:
            # check if the email is available
            other_user = await UserRepository.find_one_by_email(email)
            return other_user is None
