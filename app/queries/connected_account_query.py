from collections.abc import Sequence

from sqlalchemy import select

from app.db import db
from app.models.auth_provider import AuthProvider
from app.models.db.connected_account import ConnectedAccount


class ConnectedAccountQuery:
    @staticmethod
    async def find_user_id_by_auth_provider(provider: AuthProvider, uid: str) -> int | None:
        """
        Find a user id by auth provider and uid.
        """
        async with db() as session:
            stmt = select(ConnectedAccount.user_id).where(
                ConnectedAccount.provider == provider,
                ConnectedAccount.uid == uid,
            )
            return await session.scalar(stmt)

    @staticmethod
    async def get_provider_id_map_by_user(user_id: int) -> dict[AuthProvider, int]:
        """
        Get a map of provider ids by user id.
        """
        async with db() as session:
            stmt = select(ConnectedAccount.provider, ConnectedAccount.id).where(ConnectedAccount.user_id == user_id)
            rows: Sequence[tuple[AuthProvider, int]] = (await session.execute(stmt)).all()  # pyright: ignore[reportAssignmentType]
            return dict(rows)
