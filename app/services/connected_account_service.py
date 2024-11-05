import logging

from sqlalchemy import delete

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.models.auth_provider import AuthProvider
from app.models.db.connected_account import ConnectedAccount


class ConnectedAccountService:
    @staticmethod
    async def add_connection(provider: AuthProvider, uid: str) -> int:
        """
        Add an external account connection to the current user.

        Returns the new connection id.
        """
        user_id = auth_user(required=True).id
        async with db_commit() as session:
            connection = ConnectedAccount(
                provider=provider,
                uid=uid,
                user_id=user_id,
            )
            session.add(connection)
        logging.debug('Added account connection %d by %r to user %d', connection.id, provider, user_id)
        return connection.id

    @staticmethod
    async def remove_connection(id: int) -> None:
        """
        Remove an external account connection from the current user.
        """
        user_id = auth_user(required=True).id
        async with db_commit() as session:
            stmt = delete(ConnectedAccount).where(
                ConnectedAccount.id == id,
                ConnectedAccount.user_id == user_id,
            )
            await session.execute(stmt)
        logging.debug('Removed account connection %d from user %d', id, user_id)
