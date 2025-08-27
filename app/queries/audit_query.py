from collections.abc import Set as AbstractSet
from datetime import timedelta
from ipaddress import IPv4Address, IPv6Address

from app.db import db
from app.models.db.audit import AUDIT_TYPE_SET, AuditType
from app.models.types import UserId


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
