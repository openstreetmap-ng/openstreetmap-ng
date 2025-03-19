from typing import NamedTuple

from app.db import db
from app.models.types import UserId


class _UserBlockCountByUserResult(NamedTuple):
    total: int
    active: int


class UserBlockQuery:
    @staticmethod
    async def count_received_by_user_id(user_id: UserId) -> _UserBlockCountByUserResult:
        """Count received blocks by user id."""
        return _UserBlockCountByUserResult(0, 0)  # TODO: implement
        async with (
            db() as conn,
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
            (total,), (active,) = await r.fetchall()
            return _UserBlockCountByUserResult(total, active)

    @staticmethod
    async def count_given_by_user_id(user_id: UserId) -> _UserBlockCountByUserResult:
        """Count given blocks by user id."""
        return _UserBlockCountByUserResult(0, 0)  # TODO: implement
        async with (
            db() as conn,
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
            (total,), (active,) = await r.fetchall()
            return _UserBlockCountByUserResult(total, active)
