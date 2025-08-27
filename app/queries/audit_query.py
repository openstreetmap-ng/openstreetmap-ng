from datetime import timedelta
from ipaddress import IPv4Address, IPv6Address

from app.db import db
from app.models.db.audit import AuditType
from app.models.types import UserId


class AuditQuery:
    @staticmethod
    async def count_ip_by_user(
        user_ids: list[UserId],
        *,
        since: timedelta,
        ignore: list[AuditType] | None = None,
    ) -> dict[UserId, list[tuple[IPv4Address | IPv6Address, int]]]:
        """
        Get IP addresses with counts for each user.

        Returns dict mapping user_id to list of (ip, count) tuples,
        where count is the number of distinct users sharing that IP.
        Results are sorted by count (descending) then by IP.
        """
        if not user_ids:
            return {}

        if ignore is None:
            ignore = ['auth_api', 'rate_limit']  # type: ignore[assignment]

        # Initialize result dict with empty lists for all requested users
        result = {user_id: [] for user_id in user_ids}

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT
                    user_id, ip,
                    COUNT(*) OVER (PARTITION BY ip) as shared_count
                FROM (
                    SELECT DISTINCT user_id, ip
                    FROM audit
                    WHERE user_id = ANY(%s)
                    AND created_at >= statement_timestamp() - %s
                    AND type != ALL(%s)
                )
                ORDER BY user_id, shared_count DESC
                """,
                (user_ids, since, ignore),
            ) as r,
        ):
            # Build result dict, grouping by user_id
            current_user: UserId | None = None
            current_list: list[tuple[IPv4Address | IPv6Address, int]] = []

            for user_id, ip, count in await r.fetchall():
                if current_user != user_id:
                    current_user = user_id
                    current_list = result[user_id]
                current_list.append((ip, count))

        return result
