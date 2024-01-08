from sqlalchemy import select

from src.db import DB
from src.models.db.oauth2_application import OAuth2Application


class OAuth2ApplicationRepository:
    @staticmethod
    async def find_one_by_id(app_id: int) -> OAuth2Application | None:
        """
        Find an OAuth2 application by id.
        """

        async with DB() as session:
            return await session.get(OAuth2Application, app_id)

    @staticmethod
    async def find_by_client_id(client_id: str) -> OAuth2Application | None:
        """
        Find an OAuth2 application by client id.
        """

        async with DB() as session:
            stmt = select(OAuth2Application).where(OAuth2Application.client_id == client_id)

            return await session.scalar(stmt)
