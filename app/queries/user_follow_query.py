from typing import Any

from psycopg.rows import dict_row

from app.db import db
from app.lib.auth_context import auth_user
from app.models.db.user import User
from app.models.types import UserId


class UserFollowQuery:
    @staticmethod
    async def is_following(target_user_id: UserId) -> bool:
        """Check if the current user is following the target user."""
        user = auth_user()
        if user is None:
            return False

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT 1 FROM user_follow
                WHERE follower_id = %s AND followee_id = %s
                LIMIT 1
                """,
                (user['id'], target_user_id),
            ) as r,
        ):
            return await r.fetchone() is not None

    @staticmethod
    async def resolve_is_following(
        items: list,
        *,
        id_key: str = 'id',
        is_following_key: str = 'is_following',
    ) -> None:
        """Resolve is_following status for a list of users."""
        if not items:
            return

        user = auth_user()
        if user is None:
            return

        id_map: dict[UserId, Any] = {item[id_key]: item for item in items}

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT followee_id FROM user_follow
                WHERE follower_id = %s AND followee_id = ANY(%s)
                """,
                (user['id'], list(id_map)),
            ) as r,
        ):
            rows: list[tuple[UserId]] = await r.fetchall()
            for (followee_id,) in rows:
                id_map[followee_id][is_following_key] = True

    @staticmethod
    async def list_following(user_id: UserId, *, limit: int = 100) -> list[dict]:
        """
        Get users that the specified user is following.
        Returns minimal user data with created_at (when the follow happened).
        """
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT
                    u.id,
                    u.display_name,
                    u.avatar_type,
                    u.avatar_id,
                    uf.created_at
                FROM user_follow uf
                JOIN "user" u ON u.id = uf.followee_id
                WHERE uf.follower_id = %s
                ORDER BY uf.created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def list_followers(user_id: UserId, *, limit: int = 100) -> list[dict]:
        """
        Get users that are following the specified user.
        Returns minimal user data with created_at (when the follow happened).
        """
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT
                    u.id,
                    u.display_name,
                    u.avatar_type,
                    u.avatar_id,
                    uf.created_at
                FROM user_follow uf
                JOIN "user" u ON u.id = uf.follower_id
                WHERE uf.followee_id = %s
                ORDER BY uf.created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def count_following(user_id: UserId) -> int:
        """Count how many users the specified user is following."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT COUNT(*) FROM user_follow
                WHERE follower_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            row = await r.fetchone()
            return row[0] if row else 0

    @staticmethod
    async def count_followers(user_id: UserId) -> int:
        """Count how many users are following the specified user."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT COUNT(*) FROM user_follow
                WHERE followee_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            row = await r.fetchone()
            return row[0] if row else 0
