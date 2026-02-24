from app.config import AUTH_PROVIDER_UID_MAX_LENGTH
from app.db import db
from app.lib.auth_context import auth_user
from app.models.db.connected_account import ConnectedAccountInit
from app.models.proto.settings_connections_types import Provider
from app.services.audit_service import audit


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

        connected_account_init: ConnectedAccountInit = {
            'provider': provider,
            'uid': uid,
            'user_id': user_id,
        }

        async with db(True) as conn:
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
            await audit(
                'add_connected_account', conn, extra={'provider': provider, 'uid': uid}
            )

    @staticmethod
    async def remove_connection(provider: Provider):
        """Remove an external account connection from the current user."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await conn.execute(
                """
                DELETE FROM connected_account
                WHERE user_id = %s AND provider = %s
                """,
                (user_id, provider),
            )
            await audit('remove_connected_account', conn, extra={'provider': provider})
