from typing import NamedTuple

from psycopg.sql import Identifier

from app.config import FOLLOWS_LIST_PAGE_SIZE
from app.db import db, db_count, db_fetchcol
from app.lib.auth.context import auth_user
from app.lib.standard.pagination import (
    StandardPaginationRequestLike,
    sp_paginate_query,
)
from app.models.db.user_follow import UserFollow
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

        current_user_id = user['id']
        async with (
            db() as conn,
            await conn.execute(t"""
                SELECT
                (   SELECT EXISTS(SELECT 1 FROM user_follow
                    WHERE follower_id = {current_user_id} AND followee_id = {target_user_id})),
                (   SELECT EXISTS(SELECT 1 FROM user_follow
                    WHERE follower_id = {target_user_id} AND followee_id = {current_user_id}))
            """) as r,
        ):
            is_following, is_followed_by = await r.fetchone()  # type: ignore
            return _FollowStatusResult(is_following, is_followed_by)

    @staticmethod
    async def count_user_follows(user_id: UserId, *, followers: bool = False) -> int:
        """
        Count follow relationships for the specified user.
        If followers is True, count followers of user_id. If False, count who user_id follows.
        """
        where_column = 'followee_id' if followers else 'follower_id'
        return await db_count('user_follow', where=t'{where_column:i} = {user_id}')

    @staticmethod
    async def paginate(
        user_id: UserId,
        sp_state: StandardPaginationRequestLike,
        *,
        followers: bool,
    ):
        """
        Paginate either users followed by `user_id` (followers=False, "following")
        or users that follow `user_id` (followers=True, "followers").

        Returned rows include `is_following` indicating whether `user_id` follows
        each row's user — i.e. on the followers tab this signals mutual follow.
        """
        join_column = 'follower_id' if followers else 'followee_id'
        where_column = 'followee_id' if followers else 'follower_id'

        return await sp_paginate_query(
            UserFollow,
            sp_state,
            select=t"""
                u.id,
                u.display_name,
                u.avatar_type,
                u.avatar_id,
                uf.created_at,
                EXISTS (
                    SELECT 1 FROM user_follow
                    WHERE follower_id = uf.{where_column:i}
                      AND followee_id = u.id
                ) AS is_following
            """,
            from_=t"""
                user_follow uf
                JOIN "user" u ON u.id = uf.{join_column:i}
            """,
            where=t'uf.{where_column:i} = {user_id}',
            cursor_sql=Identifier('uf', 'created_at'),
            id_sql=Identifier('u', 'id'),
            cursor_key='created_at',
            id_key='id',
            page_size=FOLLOWS_LIST_PAGE_SIZE,
            cursor_kind='datetime',
            order_dir='desc',
        )

    @staticmethod
    async def get_followee_ids(user_id: UserId) -> list[UserId]:
        """List user ids that the user follows."""
        return await db_fetchcol(
            UserId,
            t"""
                SELECT followee_id FROM user_follow
                WHERE follower_id = {user_id}
            """,
        )
