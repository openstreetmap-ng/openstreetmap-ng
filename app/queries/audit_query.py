from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from typing import Literal, TypedDict, Unpack, overload

from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.config import AUDIT_LIST_PAGE_SIZE
from app.db import db
from app.lib.standard_pagination import standard_pagination_range
from app.models.db.audit import AuditEvent, AuditType
from app.models.db.oauth2_token import OAuth2Token
from app.models.types import ApplicationId, DisplayName, OAuth2TokenId, UserId
from app.queries.user_query import UserQuery


class AuditQuery:
    @staticmethod
    async def count_ip_by_user(
        user_ids: list[UserId],
        *,
        since: timedelta,
        ignore_app_events: bool = False,
    ) -> dict[UserId, list[tuple[IPv4Address | IPv6Address, int]]]:
        """
        Get IP addresses with counts for each user.

        Returns dict mapping user_id to list of (ip, count) tuples,
        where count is the number of distinct users sharing that IP.
        Results are sorted by count (descending).
        """
        if not user_ids:
            return {}

        ignore_app_sql = SQL('AND application_id IS NULL' if ignore_app_events else '')

        async with (
            db() as conn,
            await conn.execute(
                SQL(
                    """
                    SELECT
                        ui.user_id, ip,
                        COUNT(DISTINCT audit.user_id) as shared_count
                    FROM (
                        SELECT DISTINCT user_id, ip
                        FROM audit
                        WHERE user_id = ANY(%(user_ids)s)
                        AND created_at >= statement_timestamp() - %(since)s
                        {}
                    ) ui
                    JOIN audit USING (ip)
                    WHERE audit.user_id IS NOT NULL
                    AND created_at >= statement_timestamp() - %(since)s
                    {}
                    GROUP BY ui.user_id, ip
                    ORDER BY ui.user_id, shared_count DESC
                    """
                ).format(ignore_app_sql, ignore_app_sql),
                {'user_ids': user_ids, 'since': since},
            ) as r,
        ):
            rows: list[tuple[UserId, IPv4Address | IPv6Address, int]]
            rows = await r.fetchall()

        result = {user_id: [] for user_id in user_ids}
        current_user: UserId | None = None
        current_list: list[tuple[IPv4Address | IPv6Address, int]] = []

        for user_id, ip, count in rows:
            if current_user != user_id:
                current_user = user_id
                current_list = result[user_id]
            current_list.append((ip, count))

        return result

    @staticmethod
    async def count_ip_by_application(
        application_ids: list[ApplicationId],
        *,
        since: timedelta,
    ) -> dict[ApplicationId, list[tuple[IPv4Address | IPv6Address, int]]]:
        """
        Get IP addresses with counts for each application.

        Returns dict mapping application_id to list of (ip, count) tuples,
        where count is the number of distinct applications sharing that IP
        within the time window. Results sorted by count (descending).
        """
        if not application_ids:
            return {}

        async with (
            db() as conn,
            await conn.execute(
                SQL(
                    """
                    SELECT
                        ai.application_id, ai.ip,
                        COUNT(DISTINCT audit.application_id) AS shared_count
                    FROM (
                        SELECT DISTINCT application_id, ip
                        FROM audit
                        WHERE application_id = ANY(%(application_ids)s)
                        AND created_at >= statement_timestamp() - %(since)s
                    ) ai
                    JOIN audit USING (ip)
                    WHERE audit.application_id IS NOT NULL
                    AND created_at >= statement_timestamp() - %(since)s
                    GROUP BY ai.application_id, ai.ip
                    ORDER BY ai.application_id, shared_count DESC
                    """
                ),
                {
                    'application_ids': application_ids,
                    'since': since,
                },
            ) as r,
        ):
            rows: list[tuple[ApplicationId, IPv4Address | IPv6Address, int]]
            rows = await r.fetchall()

        result = {app_id: [] for app_id in application_ids}
        current_app: ApplicationId | None = None
        current_list: list[tuple[IPv4Address | IPv6Address, int]] = []

        for app_id, ip, count in rows:
            if current_app != app_id:
                current_app = app_id
                current_list = result[app_id]
            current_list.append((ip, count))

        return result

    class _FindParams(TypedDict, total=False):
        ip: IPv4Address | IPv6Address | IPv4Network | IPv6Network | None
        user: str | None
        application_id: ApplicationId | None
        type: AuditType | None
        created_after: datetime | None
        created_before: datetime | None

    @overload
    @staticmethod
    async def find(
        mode: Literal['count'],
        /,
        **kwargs: Unpack[_FindParams],
    ) -> int: ...

    @overload
    @staticmethod
    async def find(
        mode: Literal['page'],
        /,
        *,
        page: int,
        num_items: int,
        **kwargs: Unpack[_FindParams],
    ) -> list[AuditEvent]: ...

    @staticmethod
    async def find(
        mode: Literal['count', 'page'],
        /,
        *,
        page: int | None = None,
        num_items: int | None = None,
        **kwargs: Unpack[_FindParams],
    ) -> int | list[AuditEvent]:
        """Find audit logs. Results are always sorted by created_at DESC (most recent first)."""
        conditions: list[Composable] = []
        params: list = []

        ip = kwargs.get('ip')
        if ip is not None:
            if isinstance(ip, IPv4Network | IPv6Network):
                conditions.append(SQL('ip >= %s AND ip <= %s'))
                params.append(ip.network_address)
                params.append(ip.broadcast_address)
            else:
                conditions.append(SQL('ip = %s'))
                params.append(ip)

        user = kwargs.get('user')
        if user is not None:
            user_ids: list[UserId] = []

            # Try to parse as user ID
            try:
                user_ids.append(UserId(int(user)))
            except (ValueError, TypeError):
                pass

            # Try to find by display name
            user_by_name = await UserQuery.find_by_display_name(DisplayName(user))
            if user_by_name is not None:
                user_ids.append(user_by_name['id'])

            if not user_ids:
                # No matching user found, return empty results
                if mode == 'count':
                    return 0
                return []

            conditions.append(SQL('(user_id = ANY(%s) OR target_user_id = ANY(%s))'))
            params.append(user_ids)
            params.append(user_ids)

        application_id = kwargs.get('application_id')
        if application_id is not None:
            conditions.append(SQL('application_id = %s'))
            params.append(application_id)

        type = kwargs.get('type')
        if type is not None:
            conditions.append(SQL('type = %s'))
            params.append(type)

        created_after = kwargs.get('created_after')
        if created_after is not None:
            conditions.append(SQL('created_at >= %s'))
            params.append(created_after)

        created_before = kwargs.get('created_before')
        if created_before is not None:
            conditions.append(SQL('created_at <= %s'))
            params.append(created_before)

        where_clause = SQL(' AND ').join(conditions) if conditions else SQL('TRUE')

        if mode == 'count':
            query = SQL('SELECT COUNT(*) FROM audit WHERE {}').format(where_clause)
            async with db() as conn, await conn.execute(query, params) as r:
                return (await r.fetchone())[0]  # type: ignore

        # mode == 'page'
        assert page is not None, "Page number must be provided in 'page' mode"
        assert num_items is not None, "Number of items must be provided in 'page' mode"

        limit, offset = standard_pagination_range(
            page,
            page_size=AUDIT_LIST_PAGE_SIZE,
            num_items=num_items,
            start_from_end=False,  # Page 1 = most recent
        )

        query = SQL("""
            SELECT * FROM audit
            WHERE {}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """).format(where_clause)
        params.extend((limit, offset))

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def resolve_last_activity(tokens: list[OAuth2Token]) -> None:
        """Resolve last_activity for tokens."""
        if not tokens:
            return

        id_map: dict[OAuth2TokenId, OAuth2Token] = {t['id']: t for t in tokens}

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT DISTINCT ON (token_id) *
                FROM audit
                WHERE token_id = ANY(%s)
                ORDER BY token_id DESC, created_at DESC
                """,
                (list(id_map),),
            ) as r,
        ):
            for row in await r.fetchall():
                id_map[row['token_id']]['last_activity'] = row  # type: ignore
