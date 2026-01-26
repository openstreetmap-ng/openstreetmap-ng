from datetime import datetime
from ipaddress import ip_address, ip_network
from typing import Any, Literal, TypedDict

from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable, Identifier
from shapely import Point

from app.config import (
    DELETED_USER_EMAIL_SUFFIX,
    NEARBY_USERS_RADIUS_METERS,
)
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.user_name_blacklist import is_user_name_blacklisted
from app.models.db.element import Element
from app.models.db.user import User, UserDisplay, UserRole
from app.models.types import ApplicationId, ChangesetId, DisplayName, Email, UserId
from app.validators.email import validate_email


class _2FAStatus(TypedDict):  # noqa: N801
    has_passkeys: bool
    has_totp: bool
    has_recovery: bool


_USER_DISPLAY_SELECT = SQL(',').join([
    Identifier(k) for k in UserDisplay.__annotations__
])


class UserQuery:
    @staticmethod
    async def find_by_id(user_id: UserId) -> User | None:
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
    async def find_by_display_name(display_name: DisplayName) -> User | None:
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
    async def find_by_email(email: Email) -> User | None:
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
    async def find_by_display_name_or_email(
        display_name_or_email: DisplayName | Email,
    ):
        """Find a user by display name or email."""
        # (dot) indicates email format, display_name blacklists it
        if '.' in display_name_or_email:
            try:
                email = validate_email(display_name_or_email)
            except ValueError:
                return None
            return await UserQuery.find_by_email(email)
        return await UserQuery.find_by_display_name(DisplayName(display_name_or_email))

    @staticmethod
    async def find_by_ids(user_ids: list[UserId]) -> list[User]:
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
    async def find_by_display_names(
        display_names: list[DisplayName],
    ) -> list[User]:
        """Find users by display names."""
        if not display_names:
            return []

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM "user"
                WHERE display_name = ANY(%s)
                """,
                (display_names,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_nearby(
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
    async def check_display_name_available(
        display_name: DisplayName, *, user: User | None = None
    ):
        """Check if a display name is available."""
        # Check if the name is unchanged
        if user is None:
            user = auth_user()
        if user is not None and user['display_name'] == display_name:
            return True

        # Check if the name is blacklisted
        if is_user_name_blacklisted(display_name):
            return False

        # Check if the name is available
        other_user = await UserQuery.find_by_display_name(display_name)
        return (
            other_user is None  #
            or (user is not None and other_user['id'] == user['id'])
        )

    @staticmethod
    async def check_email_available(email: Email, *, user: User | None = None):
        """Check if an email is available."""
        # Check if the email is unchanged
        if user is None:
            user = auth_user()
        if user is not None and user['email'] == email:
            return True

        # Check if the email is available
        other_user = await UserQuery.find_by_email(email)
        return (
            other_user is None  #
            or (user is not None and other_user['id'] == user['id'])
        )

    @staticmethod
    async def find_deleted_ids(
        *,
        after: UserId | None = None,
        before: UserId | None = None,
        sort: Literal['asc', 'desc'] = 'asc',
        limit: int | None = None,
    ) -> list[UserId]:
        """Find the ids of deleted users."""
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
    ):
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
            await conn.cursor(row_factory=dict_row).execute(
                query, (list(id_map),)
            ) as r,
        ):
            for row in await r.fetchall():
                for item in id_map[row['id']]:
                    item[user_key] = row

    @staticmethod
    async def resolve_elements_users(elements: list[Element]):
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

    @staticmethod
    def where_clause(
        *,
        search: str | None = None,
        unverified: bool | None = None,
        roles: list[UserRole] | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        application_id: ApplicationId | None = None,
    ):
        conditions: list[Composable] = []
        params: list[Any] = []

        if search:
            try:
                search_ip = ip_address(search)
                conditions.append(
                    SQL("""
                        EXISTS (
                        SELECT 1 FROM audit
                        WHERE user_id = "user".id AND ip = %s
                        )
                    """)
                )
                params.append(search_ip)
            except ValueError:
                try:
                    search_ip = ip_network(search, strict=False)
                    conditions.append(
                        SQL("""
                            EXISTS (
                                SELECT 1 FROM audit
                                WHERE user_id = "user".id AND ip <<= %s
                            )
                        """)
                    )
                    params.append(search_ip)
                except ValueError:
                    conditions.append(SQL('(email ILIKE %s OR display_name ILIKE %s)'))
                    pattern = f'%{search}%'
                    params.extend((pattern, pattern))

        if unverified:
            conditions.append(SQL('NOT email_verified'))

        if roles:
            conditions.append(SQL('roles && %s'))
            params.append(roles)

        if created_after:
            conditions.append(SQL('created_at >= %s'))
            params.append(created_after)

        if created_before:
            conditions.append(SQL('created_at <= %s'))
            params.append(created_before)

        if application_id is not None:
            conditions.append(
                SQL("""
                    EXISTS (
                        SELECT 1 FROM oauth2_token
                        WHERE user_id = "user".id
                        AND application_id = %s
                        AND authorized_at IS NOT NULL
                    )
                """)
            )
            params.append(application_id)

        where_clause = SQL(' AND ').join(conditions) if conditions else SQL('TRUE')
        return where_clause, tuple(params)

    @staticmethod
    async def find_ids(
        *,
        limit: int,
        search: str | None = None,
        unverified: bool | None = None,
        roles: list[UserRole] | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        application_id: ApplicationId | None = None,
        sort: Literal['created_asc', 'created_desc'] = 'created_desc',
    ) -> list[UserId]:
        where_clause, params = UserQuery.where_clause(
            search=search,
            unverified=unverified,
            roles=roles,
            created_after=created_after,
            created_before=created_before,
            application_id=application_id,
        )

        order_dir: SQL
        if sort == 'created_desc':
            order_dir = SQL('DESC')
        elif sort == 'created_asc':
            order_dir = SQL('ASC')
        else:
            raise NotImplementedError(f'Unsupported sort {sort!r}')

        query = SQL("""
            SELECT id FROM "user"
            WHERE {where}
            ORDER BY created_at {dir}, id {dir}
            LIMIT %s
        """).format(where=where_clause, dir=order_dir)
        params = (*params, limit)

        async with db() as conn, await conn.execute(query, params) as r:
            return [c for (c,) in await r.fetchall()]

    @staticmethod
    async def get_2fa_status(user_ids: list[UserId]) -> dict[UserId, _2FAStatus]:
        """Get 2FA status for multiple users efficiently."""
        if not user_ids:
            return {}

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT
                    u.user_id,
                    EXISTS(SELECT 1 FROM user_passkey WHERE user_id = u.user_id) AS has_passkeys,
                    EXISTS(SELECT 1 FROM user_totp WHERE user_id = u.user_id) AS has_totp,
                    EXISTS(
                        SELECT 1 FROM user_recovery_code
                        WHERE user_id = u.user_id
                        AND array_remove(codes_hashed, NULL) != '{}'
                    ) AS has_recovery
                FROM unnest(%s::bigint[]) AS u(user_id)
                """,
                (user_ids,),
            ) as r,
        ):
            return {
                row[0]: _2FAStatus(
                    has_passkeys=row[1],
                    has_totp=row[2],
                    has_recovery=row[3],
                )
                for row in await r.fetchall()
            }
