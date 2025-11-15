import logging

from psycopg.rows import dict_row

from app.config import APP_URL
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.translation import t, translation_context
from app.models.db.user import User
from app.models.types import UserId
from app.queries.user_query import UserQuery
from app.services.email_service import EmailService


class UserFollowService:
    @staticmethod
    async def follow(target_user_id: UserId) -> None:
        """
        Follow a user.
        - Requires authentication
        - Prevents self-follow
        - Sends email notification to the followee on first follow
        """
        follower = auth_user(required=True)
        follower_id = follower['id']

        # Prevent self-follow
        if follower_id == target_user_id:
            raise_for.user_not_found(target_user_id)

        # Ensure target user exists
        target_user = await UserQuery.find_one_by_id(target_user_id)
        if target_user is None:
            raise_for.user_not_found(target_user_id)

        # Check if already following (to determine if we should send email)
        async with db() as conn:
            async with await conn.execute(
                """
                SELECT 1 FROM user_follow
                WHERE follower_id = %s AND followee_id = %s
                LIMIT 1
                """,
                (follower_id, target_user_id),
            ) as r:
                already_following = await r.fetchone() is not None

        # Insert follow relationship (idempotent)
        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO user_follow (follower_id, followee_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (follower_id, target_user_id),
            )

        logging.debug('User %d followed user %d', follower_id, target_user_id)

        # Send email notification only on first follow
        if not already_following:
            await UserFollowService._send_follow_notification(
                follower, target_user
            )

    @staticmethod
    async def unfollow(target_user_id: UserId) -> None:
        """
        Unfollow a user.
        - Requires authentication
        - Idempotent (no error if not following)
        """
        follower_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await conn.execute(
                """
                DELETE FROM user_follow
                WHERE follower_id = %s AND followee_id = %s
                """,
                (follower_id, target_user_id),
            )

        logging.debug('User %d unfollowed user %d', follower_id, target_user_id)

    @staticmethod
    async def _send_follow_notification(
        follower: User, followee: User
    ) -> None:
        """Send email notification to the followee about the new follow."""
        with translation_context(followee['language']):
            subject = t(
                'user_mailer.follow_notification.subject',
                user=follower['display_name'],
            )

        template_data = {
            'follower': follower,
            'followee': followee,
            'follower_profile_url': f"{APP_URL}/user/{follower['display_name']}",
            'follow_back_url': f"{APP_URL}/user/{follower['display_name']}#follow",
        }

        await EmailService.schedule(
            source=None,
            from_user_id=None,
            to_user=followee,
            subject=subject,
            template_name='email/follow',
            template_data=template_data,
        )

        logging.info(
            'Sent follow notification email from user %d to user %d',
            follower['id'],
            followee['id'],
        )
