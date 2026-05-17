from datetime import datetime
from ipaddress import ip_address, ip_network
from string.templatelib import Template
from typing import Literal, TypedDict, assert_never

from psycopg.sql import SQL, Identifier
from shapely import Point

from app.config import (
    DELETED_USER_EMAIL_SUFFIX,
    NEARBY_USERS_RADIUS_METERS,
)
from app.db import (
    db_fetchall,
    db_fetchcol,
    db_fetchone,
    db_fetchrows,
    t_and,
    t_order,
)
from app.lib.auth.context import auth_user
from app.lib.text.user_name_blacklist import is_user_name_blacklisted
from app.models.db.element import Element
from app.models.db.user import User, UserDisplay
from app.models.proto.admin_users_types import Role
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
        return await db_fetchone(
            User,
            t'SELECT * FROM "user" WHERE id = {user_id}',
        )

    @staticmethod
    async def find_by_display_name(display_name: DisplayName) -> User | None:
        """Find a user by display name."""
        return await db_fetchone(
            User,
            t'SELECT * FROM "user" WHERE display_name = {display_name}',
        )

    @staticmethod
    async def find_by_email(email: Email) -> User | None:
        """Find a user by email."""
        return await db_fetchone(
            User,
            t'SELECT * FROM "user" WHERE email = {email}',
        )

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
        return await db_fetchall(
            User,
            t'SELECT * FROM "user" WHERE id = ANY({user_ids})',
        )

    @staticmethod
    async def find_by_display_names(
        display_names: list[DisplayName],
    ) -> list[User]:
        """Find users by display names."""
        if not display_names:
            return []
        return await db_fetchall(
            User,
            t'SELECT * FROM "user" WHERE display_name = ANY({display_names})',
        )

    @staticmethod
    async def find_nearby(
        point: Point,
        *,
        max_distance: float = NEARBY_USERS_RADIUS_METERS,
        limit: int | None = None,
    ) -> list[User]:
        """Find nearby users. Users position is determined by their home point."""
        return await db_fetchall(
            User,
            t"""
                SELECT * FROM "user"
                WHERE ST_DWithin(home_point, {point}, {max_distance})
                ORDER BY home_point <-> {point}
            """,
            limit=limit,
        )

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
        email_suffix = f'%{DELETED_USER_EMAIL_SUFFIX}'
        where = t_and(
            t'email LIKE {email_suffix}',
            t'id > {after}' if after is not None else None,
            t'id < {before}' if before is not None else None,
        )
        order = t_order(sort)

        return await db_fetchcol(
            UserId,
            t"""
                SELECT id FROM "user"
                WHERE {where:q}
                ORDER BY id {order:q}
            """,
            limit=limit,
        )

    @staticmethod
    async def resolve_users(
        items: list,
        *,
        user_id_key: str = 'user_id',
        user_key: str = 'user',
        kind: type[UserDisplay | User] = UserDisplay,
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

        select_sql = _USER_DISPLAY_SELECT if kind is UserDisplay else SQL('*')
        ids = list(id_map)
        rows = await db_fetchall(
            User,
            t'SELECT {select_sql:q} FROM "user" WHERE id = ANY({ids})',
        )
        for row in rows:
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

        changeset_ids = list(id_map)
        rows = await db_fetchrows(t"""
            SELECT id, user_id FROM changeset
            WHERE id = ANY({changeset_ids})
        """)
        changeset_id: ChangesetId
        user_id: UserId | None
        for changeset_id, user_id in rows:
            if user_id is not None:
                for element in id_map[changeset_id]:
                    element['user_id'] = user_id

        await UserQuery.resolve_users(elements)

    @staticmethod
    def where_clause(
        *,
        search: str | None = None,
        unverified: bool | None = None,
        roles: list[Role] | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        application_id: ApplicationId | None = None,
    ):
        search_cond: Template | None = None
        if search:
            try:
                search_ip = ip_address(search)
                search_cond = t"""
                    EXISTS (
                        SELECT 1 FROM audit
                        WHERE user_id = "user".id AND ip = {search_ip}
                    )
                """
            except ValueError:
                try:
                    search_net = ip_network(search, strict=False)
                    search_cond = t"""
                        EXISTS (
                            SELECT 1 FROM audit
                            WHERE user_id = "user".id AND ip <<= {search_net}
                        )
                    """
                except ValueError:
                    pattern = f'%{search}%'
                    search_cond = (
                        t'(email ILIKE {pattern} OR display_name ILIKE {pattern})'
                    )

        return t_and(
            search_cond,
            t'NOT email_verified' if unverified else None,
            t'roles && {roles}' if roles else None,
            t'created_at >= {created_after}' if created_after else None,
            t'created_at <= {created_before}' if created_before else None,
            t"""
                EXISTS (
                    SELECT 1 FROM oauth2_token
                    WHERE user_id = "user".id
                    AND application_id = {application_id}
                    AND authorized_at IS NOT NULL
                )
            """
            if application_id is not None
            else None,
        )

    @staticmethod
    async def find_ids(
        *,
        limit: int,
        search: str | None = None,
        unverified: bool | None = None,
        roles: list[Role] | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        application_id: ApplicationId | None = None,
        sort: Literal['created_asc', 'created_desc'] = 'created_desc',
    ) -> list[UserId]:
        where = UserQuery.where_clause(
            search=search,
            unverified=unverified,
            roles=roles,
            created_after=created_after,
            created_before=created_before,
            application_id=application_id,
        )

        if sort == 'created_desc':
            order_dir = t_order('desc')
        elif sort == 'created_asc':
            order_dir = t_order('asc')
        else:
            assert_never(sort)

        return await db_fetchcol(
            UserId,
            t"""
                SELECT id FROM "user"
                WHERE {where:q}
                ORDER BY created_at {order_dir:q}, id {order_dir:q}
            """,
            limit=limit,
        )

    @staticmethod
    async def get_2fa_status(user_ids: list[UserId]) -> dict[UserId, _2FAStatus]:
        """Get 2FA status for multiple users efficiently."""
        if not user_ids:
            return {}

        rows = await db_fetchrows(t"""
            SELECT
                u.user_id,
                EXISTS(SELECT 1 FROM user_passkey WHERE user_id = u.user_id) AS has_passkeys,
                EXISTS(SELECT 1 FROM user_totp WHERE user_id = u.user_id) AS has_totp,
                EXISTS(
                    SELECT 1 FROM user_recovery_code
                    WHERE user_id = u.user_id
                    AND array_remove(codes_hashed, NULL) != '{{}}'
                ) AS has_recovery
            FROM unnest({user_ids}::bigint[]) AS u(user_id)
        """)
        return {
            row[0]: _2FAStatus(
                has_passkeys=row[1],
                has_totp=row[2],
                has_recovery=row[3],
            )
            for row in rows
        }
