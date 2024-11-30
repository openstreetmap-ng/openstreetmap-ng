from collections import defaultdict
from collections.abc import Collection, Sequence

from shapely import Point
from sqlalchemy import func, null, select, text

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.options_context import apply_options_context
from app.limits import NEARBY_USERS_RADIUS_METERS
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.user import User
from app.models.types import DisplayNameType, EmailType


class UserQuery:
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
    async def find_one_by_display_name(display_name: DisplayNameType) -> User | None:
        """
        Find a user by display name.
        """
        async with db() as session:
            stmt = select(User).where(User.display_name == display_name)
            stmt = apply_options_context(stmt)
            return await session.scalar(stmt)

    @staticmethod
    async def find_one_by_email(email: EmailType) -> User | None:
        """
        Find a user by email.
        """
        async with db() as session:
            stmt = select(User).where(User.email == email)
            stmt = apply_options_context(stmt)
            return await session.scalar(stmt)

    @staticmethod
    async def find_many_by_ids(user_ids: Collection[int]) -> Sequence[User]:
        """
        Find users by ids.
        """
        if not user_ids:
            return ()
        async with db() as session:
            stmt = select(User).where(User.id.in_(text(','.join(map(str, user_ids)))))
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
    async def check_display_name_available(display_name: DisplayNameType) -> bool:
        """
        Check if a display name is available.
        """
        user = auth_user()
        if user is not None:
            # check if the name is unchanged
            if user.display_name == display_name:
                return True

            # check if the name is available
            other_user = await UserQuery.find_one_by_display_name(display_name)
            return other_user is None or other_user.id == user.id

        else:
            # check if the name is available
            other_user = await UserQuery.find_one_by_display_name(display_name)
            return other_user is None

    @staticmethod
    async def check_email_available(email: EmailType) -> bool:
        """
        Check if an email is available.
        """
        user = auth_user()
        if user is not None:
            # check if the email is unchanged
            if user.email == email:
                return True

            # check if the email is available
            other_user = await UserQuery.find_one_by_email(email)
            return other_user is None or other_user.id == user.id

        else:
            # check if the email is available
            other_user = await UserQuery.find_one_by_email(email)
            return other_user is None

    @staticmethod
    async def resolve_elements_users(elements: Collection[Element], *, display_name: bool) -> None:
        """str
        Resolve the elements users ids.

        If display_name is True, the users display name is also resolved.
        """
        if not elements:
            return
        id_elements_map: defaultdict[int, list[Element]] = defaultdict(list)
        for element in elements:
            id_elements_map[element.changeset_id].append(element)

        if display_name:
            async with db() as session:
                stmt = (
                    select(Changeset.id, Changeset.user_id, User.display_name)
                    .join(User, Changeset.user_id == User.id)
                    .where(Changeset.id.in_(text(','.join(map(str, id_elements_map)))))
                )
                rows = (await session.execute(stmt)).all()
            for changeset_id, user_id, display_name_str in rows:
                for element in id_elements_map[changeset_id]:
                    element.user_id = user_id
                    element.user_display_name = display_name_str
        else:
            async with db() as session:
                stmt2 = select(Changeset.id, Changeset.user_id).where(
                    Changeset.id.in_(text(','.join(map(str, id_elements_map))))
                )
                rows = (await session.execute(stmt2)).all()
            for changeset_id, user_id in rows:
                for element in id_elements_map[changeset_id]:
                    element.user_id = user_id
                    element.user_display_name = None

    # @staticmethod
    # async def resolve_note_comments_users(comments: Sequence[NoteComment]) -> None:
    #     """
    #     Resolve the user of note comments.
    #     """
    #     comments_ = []
    #     user_id_comments_map = defaultdict(list)
    #     for comment in comments:
    #         if comment.user_id is not None and comment.user is None:
    #             comments_.append(comment)
    #             user_id_comments_map[comment.user_id].append(comment)

    #     if not comments_:
    #         return

    #     async with db() as session:
    #         stmt = select(User).where(User.id.in_(text(','.join(map(str, user_id_comments_map)))))
    #         stmt = apply_options_context(stmt)
    #         users = (await session.scalars(stmt)).all()

    #     for user in users:
    #         for comment in user_id_comments_map[user.id]:
    #             comment.user = user
