import logging

from app.db import db
from app.lib.auth_context import auth_user
from app.limits import AUTH_PROVIDER_UID_MAX_LENGTH
from app.models.db.connected_account import AuthProvider, ConnectedAccountInit


class ConnectedAccountService:
    @staticmethod
    async def add_connection(provider: AuthProvider, uid: str) -> None:
        """
        Add an external account connection to the current user.
        Returns the user_id.
        """
        if len(uid) > AUTH_PROVIDER_UID_MAX_LENGTH:
            raise ValueError(f'Connected account uid too long: {len(uid)} > {AUTH_PROVIDER_UID_MAX_LENGTH}')

        user_id = auth_user(required=True)['id']

        connected_account_init: ConnectedAccountInit = {
            'provider': provider,
            'uid': uid,
            'user_id': user_id,
        }

        async with db(write=True) as conn:
            await conn.execute(
                """
                INSERT INTO connected_account (
                    user_id, provider, uid
                )
                VALUES (
                    %(user_id)s, %(provider)s, %(uid)s
                )
                """,
                connected_account_init,
            )

        logging.debug('Added account connection %r to user %d', provider, user_id)

    @staticmethod
    async def remove_connection(provider: AuthProvider) -> None:
        """Remove an external account connection from the current user."""
        user_id = auth_user(required=True)['id']

        async with db(write=True) as conn:
            await conn.execute(
                """
                DELETE FROM connected_account
                WHERE user_id = %s AND provider = %s
                """,
                (user_id, provider),
            )

        logging.debug('Removed account connection %r from user %d', provider, user_id)
