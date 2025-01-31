from collections.abc import Sequence

from sqlalchemy import select

from app.db import db
from app.lib.options_context import apply_options_context
from app.models.db.oauth2_application import OAuth2Application


class OAuth2ApplicationQuery:
    @staticmethod
    async def find_one_by_id(app_id: int, *, user_id: int | None = None) -> OAuth2Application | None:
        """Find an OAuth2 application by id."""
        async with db() as session:
            stmt = select(OAuth2Application)
            stmt = apply_options_context(stmt)
            where_and = [OAuth2Application.id == app_id]

            if user_id is not None:
                where_and.append(OAuth2Application.user_id == user_id)

            stmt = stmt.where(*where_and)
            return await session.scalar(stmt)

    @staticmethod
    async def find_one_by_client_id(client_id: str) -> OAuth2Application | None:
        """Find an OAuth2 application by client id."""
        async with db() as session:
            stmt = select(OAuth2Application).where(OAuth2Application.client_id == client_id)
            stmt = apply_options_context(stmt)
            return await session.scalar(stmt)

    @staticmethod
    async def get_many_by_user_id(user_id: int) -> Sequence[OAuth2Application]:
        """Get all OAuth2 applications by user id."""
        async with db() as session:
            stmt = (
                select(OAuth2Application)
                .where(OAuth2Application.user_id == user_id)
                .order_by(OAuth2Application.id.desc())
            )
            stmt = apply_options_context(stmt)
            return (await session.scalars(stmt)).all()
