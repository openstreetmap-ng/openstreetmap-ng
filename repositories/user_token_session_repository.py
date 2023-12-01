from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from db import DB
from models.db.user_token_session import UserTokenSession


class UserTokenSessionRepository:
    @staticmethod
    async def find_one_by_id(session_id: UUID) -> UserTokenSession | None:
        """
        Find a user session token by id.
        """

        async with DB() as session:
            stmt = (
                select(UserTokenSession)
                .options(joinedload(UserTokenSession.user))
                .where(
                    UserTokenSession.id == session_id,
                    UserTokenSession.expires_at > func.now(),  # TODO: expires at check
                )
            )

            return await session.scalar(stmt)
