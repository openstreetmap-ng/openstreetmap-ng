import logging

from app.db import db
from app.lib.auth_context import auth_user
from app.models.types import UserId
from app.queries.user_query import UserQuery


class UserFollowService:
    @staticmethod
    async def follow(target_user_id: UserId) -> None:
        follower_id = auth_user(required=True)['id']

        # Prevent self-follow
        if follower_id == target_user_id:
            return

        # Ensure target user exists
        target_user = await UserQuery.find_by_id(target_user_id)
        if target_user is None:
            return

        async with (
            db(True) as conn,
            await conn.execute(
                """
                INSERT INTO user_follow (follower_id, followee_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                RETURNING follower_id
                """,
                (follower_id, target_user_id),
            ) as r,
        ):
            if await r.fetchone() is None:
                # Do nothing on existing follow
                return

        logging.debug('User %d followed user %d', follower_id, target_user_id)

    @staticmethod
    async def unfollow(target_user_id: UserId) -> None:
        follower_id = auth_user(required=True)['id']

        async with db(True) as conn:
            result = await conn.execute(
                """
                DELETE FROM user_follow
                WHERE follower_id = %s AND followee_id = %s
                """,
                (follower_id, target_user_id),
            )

            if result.rowcount:
                logging.debug('User %d unfollowed user %d', follower_id, target_user_id)
