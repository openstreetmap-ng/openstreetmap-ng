from typing import NamedTuple

from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier

from app.config import FOLLOWS_LIST_PAGE_SIZE
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.standard_pagination import standard_pagination_range
from app.models.db.user_follow import UserFollowDisplay
from app.models.types import UserId


class _FollowStatusResult(NamedTuple):
    is_following: bool
    is_followed_by: bool


class UserFollowQuery:
    @staticmethod
    async def get_follow_status(target_user_id: UserId) -> _FollowStatusResult:
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
    async def list_user_follows(
        user_id: UserId,
        *,
        followers: bool = False,
        page: int,
        num_items: int,
    ) -> list[UserFollowDisplay]:
        """
        Get a paginated list of users related to the specified user by follow relationship.
        If followers is True, get followers of user_id. If False, get who user_id follows.
        """
        stmt_limit, stmt_offset = standard_pagination_range(
            page,
            page_size=FOLLOWS_LIST_PAGE_SIZE,
            num_items=num_items,
            reverse=False,
        )

        user = auth_user()
        current_user_id = user['id'] if user is not None else None

        if followers:
            # Get people following user_id
            join_column = Identifier('follower_id')
            where_column = Identifier('followee_id')
        else:
            # Get people user_id is following
            join_column = Identifier('followee_id')
            where_column = Identifier('follower_id')

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                SQL(
                    """
                    SELECT
                        u.id,
                        u.display_name,
                        u.avatar_type,
                        u.avatar_id,
                        uf.created_at,
                        EXISTS (
                            SELECT 1 FROM user_follow
                            WHERE follower_id = %s AND followee_id = u.id
                        ) AS is_following
                    FROM user_follow uf
                    JOIN "user" u ON u.id = uf.{join_column}
                    WHERE uf.{where_column} = %s
                    ORDER BY uf.created_at DESC
                    LIMIT %s OFFSET %s
                    """
                ).format(join_column=join_column, where_column=where_column),
                (current_user_id, user_id, stmt_limit, stmt_offset),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

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
