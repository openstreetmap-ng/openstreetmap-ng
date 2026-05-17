import logging

from app.config import USER_PENDING_EXPIRE, USER_SCHEDULED_DELETE_DELAY
from app.db import db_delete, db_update
from app.lib.auth.context import auth_user


class UserLifecycleService:
    # TODO: UI
    @staticmethod
    async def request_scheduled_delete():
        """Request a scheduled deletion of the user."""
        user_id = auth_user(required=True)['id']

        await db_update(
            'user',
            {
                'scheduled_delete_at': t'statement_timestamp() + {USER_SCHEDULED_DELETE_DELAY}'
            },
            where=t'id = {user_id} AND scheduled_delete_at IS NULL',
        )

    @staticmethod
    async def abort_scheduled_delete():
        """Abort a scheduled deletion of the user."""
        user_id = auth_user(required=True)['id']

        await db_update(
            'user',
            {'scheduled_delete_at': None},
            where={'id': user_id},
        )

    @staticmethod
    async def delete_old_pending_users():
        """Find old pending users and delete them."""
        logging.debug('Deleting old pending users')

        await db_delete(
            'user',
            where=t'NOT email_verified AND created_at < statement_timestamp() - {USER_PENDING_EXPIRE}',
        )
