from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from typing import Any

from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.db import db
from app.models.db.oauth2_token import OAuth2Token
from app.models.proto.audit_types import Type
from app.models.types import ApplicationId, DisplayName, OAuth2TokenId, UserId
from app.queries.user_query import UserQuery


class AuditQuery:
    @staticmethod
    async def count_ip_by_user(
        user_ids: list[UserId],
        *,
        since: timedelta,
        ignore_app_events: bool = False,
        limit: int | None = None,
    ) -> dict[UserId, list[tuple[IPv4Address | IPv6Address, int]]]:
        """
        Get IP addresses with counts for each user.

        Returns dict mapping user_id to list of (ip, count) tuples,
        where count is the number of distinct users sharing that IP.
        Results are sorted by count (descending).
        """
        if not user_ids:
            return {}

        async with (
            db() as conn,
            await conn.execute(
                SQL(
                    """
                    WITH seed AS (
                        SELECT DISTINCT user_id, ip
                        FROM audit
                        WHERE user_id = ANY(%(user_ids)s)
                        AND created_at >= statement_timestamp() - %(since)s
                        AND (NOT %(ignore_app_events)s OR application_id IS NULL)
                    ),
                    counts AS (
                        SELECT ip, COUNT(DISTINCT user_id) AS shared_count
                        FROM audit
                        JOIN (SELECT DISTINCT ip FROM seed) seed_ips USING (ip)
                        WHERE user_id IS NOT NULL
                        AND created_at >= statement_timestamp() - %(since)s
                        AND (NOT %(ignore_app_events)s OR application_id IS NULL)
                        GROUP BY ip
                    ),
                    ranked AS (
                        SELECT
                            user_id,
                            ip,
                            shared_count,
                            ROW_NUMBER() OVER (
                                PARTITION BY user_id
                                ORDER BY shared_count DESC, ip
                            ) AS rank_num
                        FROM seed
                        JOIN counts USING (ip)
                    )
                    SELECT user_id, ip, shared_count
                    FROM ranked
                    WHERE rank_num <= COALESCE(%(limit)s, rank_num)
                    ORDER BY user_id, shared_count DESC, ip
                    """
                ),
                {
                    'user_ids': user_ids,
                    'since': since,
                    'ignore_app_events': ignore_app_events,
                    'limit': limit,
                },
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
        limit: int | None = None,
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
                    WITH seed AS (
                        SELECT DISTINCT application_id, ip
                        FROM audit
                        WHERE application_id = ANY(%(application_ids)s)
                        AND created_at >= statement_timestamp() - %(since)s
                    ),
                    counts AS (
                        SELECT ip, COUNT(DISTINCT application_id) AS shared_count
                        FROM audit
                        JOIN (SELECT DISTINCT ip FROM seed) seed_ips USING (ip)
                        WHERE application_id IS NOT NULL
                        AND created_at >= statement_timestamp() - %(since)s
                        GROUP BY ip
                    ),
                    ranked AS (
                        SELECT
                            application_id,
                            ip,
                            shared_count,
                            ROW_NUMBER() OVER (
                                PARTITION BY application_id
                                ORDER BY shared_count DESC, ip
                            ) AS rank_num
                        FROM seed
                        JOIN counts USING (ip)
                    )
                    SELECT application_id, ip, shared_count
                    FROM ranked
                    WHERE rank_num <= COALESCE(%(limit)s, rank_num)
                    ORDER BY application_id, shared_count DESC, ip
                    """
                ),
                {
                    'application_ids': application_ids,
                    'since': since,
                    'limit': limit,
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

    @staticmethod
    async def where_clause(
        *,
        ip: IPv4Address | IPv6Address | IPv4Network | IPv6Network | None = None,
        user: str | None = None,
        application_id: ApplicationId | None = None,
        type: Type | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
    ):
        """Build the WHERE clause for audit log filters."""
        conditions: list[Composable] = []
        params: list[Any] = []

        if ip is not None:
            if isinstance(ip, IPv4Network | IPv6Network):
                conditions.append(SQL('ip BETWEEN %s AND %s'))
                params.append(ip.network_address)
                params.append(ip.broadcast_address)
            else:
                conditions.append(SQL('ip = %s'))
                params.append(ip)

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
                return SQL('FALSE'), ()

            conditions.append(SQL('(user_id = ANY(%s) OR target_user_id = ANY(%s))'))
            params.append(user_ids)
            params.append(user_ids)

        if application_id is not None:
            conditions.append(SQL('application_id = %s'))
            params.append(application_id)

        if type is not None:
            conditions.append(SQL('type = %s'))
            params.append(type)

        if created_after is not None:
            conditions.append(SQL('created_at >= %s'))
            params.append(created_after)

        if created_before is not None:
            conditions.append(SQL('created_at <= %s'))
            params.append(created_before)

        where_clause = SQL(' AND ').join(conditions or (SQL('TRUE'),))
        return where_clause, tuple(params)

    @staticmethod
    async def resolve_last_activity(tokens: list[OAuth2Token]):
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
                ORDER BY token_id DESC, created_at DESC, id DESC
                """,
                (list(id_map),),
            ) as r,
        ):
            for row in await r.fetchall():
                id_map[row['token_id']]['last_activity'] = row  # type: ignore
