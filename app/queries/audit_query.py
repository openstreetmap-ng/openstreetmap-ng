from collections.abc import Set as AbstractSet
from datetime import timedelta
from ipaddress import IPv4Address, IPv6Address
from typing import Literal

from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.config import AUDIT_LIST_PAGE_SIZE
from app.db import db
from app.lib.standard_pagination import standard_pagination_range
from app.models.db.audit import AUDIT_TYPE_SET, AuditEvent, AuditType
from app.models.types import ApplicationId, UserId


class AuditQuery:
    @staticmethod
    async def count_ip_by_user(
        user_ids: list[UserId],
        *,
        since: timedelta,
        ignore: AbstractSet[AuditType] = {'auth_api', 'rate_limit'},  # type: ignore
    ) -> dict[UserId, list[tuple[IPv4Address | IPv6Address, int]]]:
        """
        Get IP addresses with counts for each user.

        Returns dict mapping user_id to list of (ip, count) tuples,
        where count is the number of distinct users sharing that IP.
        Results are sorted by count (descending) then by IP.
        """
        if not user_ids:
            return {}

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT
                    ui.user_id, ui.ip,
                    COUNT(DISTINCT a.user_id) as shared_count
                FROM (
                    SELECT DISTINCT user_id, ip
                    FROM audit
                    WHERE user_id = ANY(%(user_ids)s)
                    AND created_at >= statement_timestamp() - %(since)s
                    AND type = ANY(%(types)s)
                ) ui
                JOIN audit a ON a.ip = ui.ip
                WHERE a.created_at >= statement_timestamp() - %(since)s
                AND a.type = ANY(%(types)s)
                GROUP BY ui.user_id, ui.ip
                ORDER BY ui.user_id, shared_count DESC
                """,
                {
                    'user_ids': user_ids,
                    'since': since,
                    'types': list(AUDIT_TYPE_SET - ignore),
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
        mode: Literal['count', 'page'],
        /,
        *,
        page: int | None = None,
        num_items: int | None = None,
        ip: IPv4Address | IPv6Address | None = None,
        user_id: UserId | None = None,
        application_id: ApplicationId | None = None,
        type: AuditType | None = None,
    ) -> int | list[AuditEvent]:
        """Find audit logs. Results are always sorted by created_at DESC (most recent first)."""
        assert ip is None or (user_id is None and application_id is None), (
            'IP filter cannot be used with user_id/application_id filters'
        )

        conditions: list[Composable] = []
        params: list = []

        if ip is not None:
            conditions.append(SQL('ip = %s'))
            params.append(ip)

        if user_id is not None:
            conditions.append(SQL('user_id = %s'))
            params.append(user_id)

        if application_id is not None:
            conditions.append(SQL('application_id = %s'))
            params.append(application_id)

        if type is not None:
            conditions.append(SQL('type = %s'))
            params.append(type)

        where_clause = SQL(' AND ').join(conditions) if conditions else SQL('TRUE')

        if mode == 'count':
            query = SQL('SELECT COUNT(*) FROM audit WHERE {}').format(where_clause)
            async with db() as conn, await conn.execute(query, params) as r:
                return (await r.fetchone())[0]  # type: ignore

        # mode == 'page'
        assert page is not None, "Page number must be provided in 'page' mode"
        assert num_items is not None, "Number of items must be provided in 'page' mode"

        stmt_limit, stmt_offset = standard_pagination_range(
            page,
            page_size=AUDIT_LIST_PAGE_SIZE,
            num_items=num_items,
            reverse=False,  # Page 1 = most recent
        )

        query = SQL("""
            SELECT * FROM audit
            WHERE {}
            ORDER BY created_at DESC
            OFFSET %s
            LIMIT %s
        """).format(where_clause)
        params.extend([stmt_offset, stmt_limit])

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore
