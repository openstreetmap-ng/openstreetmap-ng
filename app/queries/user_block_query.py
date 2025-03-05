from typing import NamedTuple

from app.db import db2
from app.models.db.user import UserId


class _UserBlockCountByUserResult(NamedTuple):
    total: int
    active: int


class UserBlockQuery:
    @staticmethod
    async def count_received_by_user_id(user_id: UserId) -> _UserBlockCountByUserResult:
        """Count received blocks by user id."""
        async with (
            db2() as conn,
            await conn.execute(
                """
                SELECT COUNT(*) FROM user_block
                WHERE to_user_id = %s
                UNION ALL
                SELECT COUNT(*) FROM user_block
                WHERE to_user_id = %s AND NOT expired
                """,
                (user_id, user_id),
            ) as r,
        ):
            rows_iter = iter(await r.fetchall())
            return _UserBlockCountByUserResult(
                total=next(rows_iter)[0],
                active=next(rows_iter)[0],
            )

    @staticmethod
    async def count_given_by_user_id(user_id: UserId) -> _UserBlockCountByUserResult:
        """Count given blocks by user id."""
        async with (
            db2() as conn,
            await conn.execute(
                """
                SELECT COUNT(*) FROM user_block
                WHERE from_user_id = %s
                UNION ALL
                SELECT COUNT(*) FROM user_block
                WHERE from_user_id = %s AND NOT expired
                """,
                (user_id, user_id),
            ) as r,
        ):
            rows_iter = iter(await r.fetchall())
            return _UserBlockCountByUserResult(
                total=next(rows_iter)[0],
                active=next(rows_iter)[0],
            )
