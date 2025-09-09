from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from typing import Literal

from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.config import AUDIT_LIST_PAGE_SIZE
from app.db import db
from app.lib.standard_pagination import (
    compute_page_cursors_bin as _compute_page_cursors_bin,
)
from app.lib.standard_pagination import (
    where_between_sql,
)
from app.models.db.audit import AuditEvent, AuditType
from app.models.types import ApplicationId, DisplayName, UserId
from app.queries.user_query import UserQuery


class AuditQuery:
    @staticmethod
    async def count_ip_by_user(
        user_ids: list[UserId],
        *,
        since: timedelta,
        ignore_types: list[AuditType] = ['auth_api', 'rate_limit'],  # type: ignore  # noqa: B006
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
                        AND type != ALL(%(ignore_types)s)
                        {}
                    ) ui
                    JOIN audit USING (ip)
                    WHERE audit.user_id IS NOT NULL
                    AND created_at >= statement_timestamp() - %(since)s
                    AND type != ALL(%(ignore_types)s)
                    {}
                    GROUP BY ui.user_id, ip
                    ORDER BY ui.user_id, shared_count DESC
                    """
                ).format(ignore_app_sql, ignore_app_sql),
                {
                    'user_ids': user_ids,
                    'since': since,
                    'ignore_types': ignore_types,
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
    async def find(
        mode: Literal['count', 'window'],
        /,
        *,
        start: str | None = None,
        end: str | None = None,
        ip: IPv4Address | IPv6Address | IPv4Network | IPv6Network | None = None,
        user: str | None = None,
        application_id: ApplicationId | None = None,
        type: AuditType | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
    ) -> int | list[AuditEvent]:
        """Find audit logs. Results are always sorted by created_at DESC (most recent first)."""
        where_clause, params = await _build_filters(
            ip=ip,
            user=user,
            application_id=application_id,
            type=type,
            created_after=created_after,
            created_before=created_before,
        )

        if mode == 'count':
            query = SQL('SELECT COUNT(*) FROM audit WHERE {}').format(where_clause)
            async with db() as conn, await conn.execute(query, params) as r:
                return (await r.fetchone())[0]  # type: ignore

        # mode == 'window'
        assert start is not None, "Start cursor must be provided in 'window' mode"
        # Normalize empty end to None
        end_val = end or None

        window_sql, window_params = where_between_sql(
            primary_col='created_at',
            order='desc',
            time_ordered=True,
            start=start,
            end=end_val,
        )
        query = SQL(
            """
            SELECT * FROM audit
            WHERE {} AND {}
            ORDER BY created_at DESC
            """
        ).format(where_clause, window_sql)
        q_params = [*params, *window_params]

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, q_params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def compute_page_cursors_bin(
        *,
        ip: IPv4Address | IPv6Address | IPv4Network | IPv6Network | None = None,
        user: str | None = None,
        application_id: ApplicationId | None = None,
        type: AuditType | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
    ) -> str:
        where_clause, params = await _build_filters(
            ip=ip,
            user=user,
            application_id=application_id,
            type=type,
            created_after=created_after,
            created_before=created_before,
        )
        base_sql = SQL('SELECT created_at FROM audit WHERE {}').format(where_clause)
        async with db() as conn:
            return await _compute_page_cursors_bin(
                conn,
                base_sql,
                params,
                primary_col='created_at',
                page_size=AUDIT_LIST_PAGE_SIZE,
                order='desc',
                time_ordered=True,
            )


async def _build_filters(
    *,
    ip: IPv4Address | IPv6Address | IPv4Network | IPv6Network | None = None,
    user: str | None = None,
    application_id: ApplicationId | None = None,
    type: AuditType | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> tuple[Composable, list]:
    conditions: list[Composable] = []
    params: list = []

    if ip is not None:
        if isinstance(ip, IPv4Network | IPv6Network):
            conditions.append(SQL('ip >= %s AND ip <= %s'))
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
            # Force no results
            return SQL('FALSE'), []

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

    where_clause = SQL(' AND ').join(conditions) if conditions else SQL('TRUE')
    return where_clause, params
