import logging

from app.config import USER_PENDING_EXPIRE, USER_SCHEDULED_DELETE_DELAY
from app.db import db
from app.lib.auth.context import auth_user


class UserLifecycleService:
    # TODO: UI
    @staticmethod
    async def request_scheduled_delete():
        """Request a scheduled deletion of the user."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await conn.execute(
                """
                UPDATE "user"
                SET scheduled_delete_at = statement_timestamp() + %s
                WHERE id = %s AND scheduled_delete_at IS NULL
                """,
                (USER_SCHEDULED_DELETE_DELAY, user_id),
            )

    @staticmethod
    async def abort_scheduled_delete():
        """Abort a scheduled deletion of the user."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await conn.execute(
                """
                UPDATE "user"
                SET scheduled_delete_at = NULL
                WHERE id = %s
                """,
                (user_id,),
            )

    @staticmethod
    async def delete_old_pending_users():
        """Find old pending users and delete them."""
        logging.debug('Deleting old pending users')

        async with db(True) as conn:
            await conn.execute(
                """
                DELETE FROM "user"
                WHERE NOT email_verified
                AND created_at < statement_timestamp() - %s
                """,
                (USER_PENDING_EXPIRE,),
            )
