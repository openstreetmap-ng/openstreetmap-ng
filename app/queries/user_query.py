from typing import Any, Literal

from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable, Identifier
from shapely import Point

from app.config import DELETED_USER_EMAIL_SUFFIX, NEARBY_USERS_RADIUS_METERS
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.user_name_blacklist import is_user_name_blacklisted
from app.models.db.element import Element
from app.models.db.user import User, UserDisplay
from app.models.types import ChangesetId, DisplayName, Email, UserId

_USER_DISPLAY_SELECT = SQL(',').join([Identifier(k) for k in UserDisplay.__annotations__])


class UserQuery:
    @staticmethod
    async def find_one_by_id(user_id: UserId) -> User | None:
        """Find a user by id."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM "user"
                WHERE id = %s
                """,
                (user_id,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def find_one_by_display_name(display_name: DisplayName) -> User | None:
        """Find a user by display name."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM "user"
                WHERE display_name = %s
                """,
                (display_name,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def find_one_by_email(email: Email) -> User | None:
        """Find a user by email."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM "user"
                WHERE email = %s
                """,
                (email,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def find_many_by_ids(user_ids: list[UserId]) -> list[User]:
        """Find users by ids."""
        if not user_ids:
            return []

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM "user"
                WHERE id = ANY(%s)
                """,
                (user_ids,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_many_nearby(
        point: Point,
        *,
        max_distance: float = NEARBY_USERS_RADIUS_METERS,
        limit: int | None = None,
    ) -> list[User]:
        """Find nearby users. Users position is determined by their home point."""
        params: list[Any] = [point, max_distance, point]

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        query = SQL("""
            SELECT * FROM "user"
            WHERE ST_DWithin(home_point, %s, %s)
            ORDER BY home_point <-> %s
            {limit}
        """).format(limit=limit_clause)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def check_display_name_available(display_name: DisplayName) -> bool:
        """Check if a display name is available."""
        # Check if the name is unchanged
        user = auth_user()
        if user is not None and user['display_name'] == display_name:
            return True

        # Check if the name is blacklisted
        if is_user_name_blacklisted(display_name):
            return False

        # Check if the name is available
        other_user = await UserQuery.find_one_by_display_name(display_name)
        return other_user is None or (user is not None and other_user['id'] == user['id'])

    @staticmethod
    async def check_email_available(email: Email) -> bool:
        """Check if an email is available."""
        # Check if the email is unchanged
        user = auth_user()
        if user is not None and user['email'] == email:
            return True

        # Check if the email is available
        other_user = await UserQuery.find_one_by_email(email)
        return other_user is None or (user is not None and other_user['id'] == user['id'])

    @staticmethod
    async def get_deleted_ids(
        *,
        after: UserId | None = None,
        before: UserId | None = None,
        sort: Literal['asc', 'desc'] = 'asc',
        limit: int | None = None,
    ) -> list[UserId]:
        """Get the ids of deleted users."""
        conditions: list[Composable] = [SQL('email LIKE %s')]
        params: list[Any] = [f'%{DELETED_USER_EMAIL_SUFFIX}']

        if after is not None:
            conditions.append(SQL('id > %s'))
            params.append(after)

        if before is not None:
            conditions.append(SQL('id < %s'))
            params.append(before)

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        query = SQL("""
            SELECT id FROM "user"
            WHERE {conditions}
            ORDER BY id {order}
            {limit}
        """).format(
            conditions=SQL(' AND ').join(conditions),
            order=SQL(sort),
            limit=limit_clause,
        )

        async with db() as conn, await conn.execute(query, params) as r:
            return [c for (c,) in await r.fetchall()]

    @staticmethod
    async def resolve_users(
        items: list,
        *,
        user_id_key: str = 'user_id',
        user_key: str = 'user',
        kind: type[UserDisplay] | type[User] = UserDisplay,
    ) -> None:
        """Resolve user fields for the given items."""
        if not items:
            return

        id_map: dict[UserId, list] = {}
        for item in items:
            user_id: UserId | None = item.get(user_id_key)
            if user_id is None:
                continue
            list_ = id_map.get(user_id)
            if list_ is None:
                id_map[user_id] = [item]
            else:
                list_.append(item)

        if not id_map:
            return

        query = SQL("""
            SELECT {} FROM "user"
            WHERE id = ANY(%s)
        """).format(_USER_DISPLAY_SELECT if kind is UserDisplay else SQL('*'))

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, (list(id_map),)) as r,
        ):
            for row in await r.fetchall():
                for item in id_map[row['id']]:
                    item[user_key] = row

    @staticmethod
    async def resolve_elements_users(elements: list[Element]) -> None:
        """Resolve the user_id and user fields for the given elements."""
        if not elements:
            return

        id_map: dict[ChangesetId, list[Element]] = {}
        for element in elements:
            changeset_id = element['changeset_id']
            list_ = id_map.get(changeset_id)
            if list_ is None:
                id_map[changeset_id] = [element]
            else:
                list_.append(element)

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT id, user_id FROM changeset
                WHERE id = ANY(%s)
                """,
                (list(id_map),),
            ) as r,
        ):
            changeset_id: ChangesetId
            user_id: UserId | None
            for changeset_id, user_id in await r.fetchall():
                if user_id is not None:
                    for element in id_map[changeset_id]:
                        element['user_id'] = user_id

        await UserQuery.resolve_users(elements)
