from app.config import AUTH_PROVIDER_UID_MAX_LENGTH
from app.db import db, db_delete, db_insert
from app.lib.audit import audit
from app.lib.auth.context import auth_user
from app.models.proto.settings_connections_types import Provider


class ConnectedAccountService:
    @staticmethod
    async def add_connection(provider: Provider, uid: str):
        """
        Add an external account connection to the current user.
        Returns the user_id.
        """
        if len(uid) > AUTH_PROVIDER_UID_MAX_LENGTH:
            raise ValueError(
                f'Connected account uid too long: {len(uid)} > {AUTH_PROVIDER_UID_MAX_LENGTH}'
            )

        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await db_insert(
                'connected_account',
                {'user_id': user_id, 'provider': provider, 'uid': uid},
                conn=conn,
            )
            await audit(
                'add_connected_account', conn, extra={'provider': provider, 'uid': uid}
            )

    @staticmethod
    async def remove_connection(provider: Provider):
        """Remove an external account connection from the current user."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await db_delete(
                'connected_account',
                where={'user_id': user_id, 'provider': provider},
                conn=conn,
            )
            await audit('remove_connected_account', conn, extra={'provider': provider})
