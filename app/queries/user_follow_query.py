from typing import NamedTuple

from psycopg.sql import SQL, Identifier

from app.db import db
from app.lib.auth_context import auth_user
from app.models.types import UserId


class _FollowStatusResult(NamedTuple):
    is_following: bool
    is_followed_by: bool


class UserFollowQuery:
    @staticmethod
    async def get_follow_status(target_user_id: UserId):
        """Get follow status between current user and target user."""
        user = auth_user()
        if user is None:
            return _FollowStatusResult(False, False)

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT
                (   SELECT EXISTS(SELECT 1 FROM user_follow
                    WHERE follower_id = %(current_user_id)s AND followee_id = %(target_user_id)s)),
                (   SELECT EXISTS(SELECT 1 FROM user_follow
                    WHERE follower_id = %(target_user_id)s AND followee_id = %(current_user_id)s))
                """,
                {'current_user_id': user['id'], 'target_user_id': target_user_id},
            ) as r,
        ):
            is_following, is_followed_by = await r.fetchone()  # type: ignore
            return _FollowStatusResult(is_following, is_followed_by)

    @staticmethod
    async def count_user_follows(user_id: UserId, *, followers: bool = False) -> int:
        """
        Count follow relationships for the specified user.
        If followers is True, count followers of user_id. If False, count who user_id follows.
        """
        async with (
            db() as conn,
            await conn.execute(
                SQL(
                    """
                    SELECT COUNT(*) FROM user_follow
                    WHERE {where_column} = %s
                    """
                ).format(
                    where_column=Identifier(
                        'followee_id' if followers else 'follower_id'
                    )
                ),
                (user_id,),
            ) as r,
        ):
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def get_followee_ids(user_id: UserId) -> list[UserId]:
        """List user ids that the user follows."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT followee_id FROM user_follow
                WHERE follower_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            return [c for (c,) in await r.fetchall()]
