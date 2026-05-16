import logging

from app.db import db_delete, db_insert
from app.lib.auth.context import auth_user
from app.models.types import UserId
from app.queries.user_query import UserQuery


class UserFollowService:
    @staticmethod
    async def follow(target_user_id: UserId):
        follower_id = auth_user(required=True)['id']

        # Prevent self-follow
        if follower_id == target_user_id:
            return

        # Ensure target user exists
        target_user = await UserQuery.find_by_id(target_user_id)
        if target_user is None:
            return

        inserted = await db_insert(
            'user_follow',
            {'follower_id': follower_id, 'followee_id': target_user_id},
            on_conflict=t'DO NOTHING',
            returning='follower_id',
            assert_returning=False,
        )
        if inserted is None:
            # Do nothing on existing follow
            return

        logging.debug('User %d followed user %d', follower_id, target_user_id)

    @staticmethod
    async def unfollow(target_user_id: UserId):
        follower_id = auth_user(required=True)['id']

        rowcount = await db_delete(
            'user_follow',
            where={'follower_id': follower_id, 'followee_id': target_user_id},
        )

        if rowcount:
            logging.debug('User %d unfollowed user %d', follower_id, target_user_id)
