from sqlalchemy import select

from app.db import db
from app.models.db.oauth1_application import OAuth1Application


class OAuth1ApplicationQuery:
    @staticmethod
    async def find_one_by_id(app_id: int) -> OAuth1Application | None:
        """
        Find an OAuth1 application by id.
        """
        async with db() as session:
            return await session.get(OAuth1Application, app_id)

    @staticmethod
    async def find_by_consumer_key(consumer_key: str) -> OAuth1Application | None:
        """
        Find an OAuth1 application by consumer key.
        """
        async with db() as session:
            stmt = select(OAuth1Application).where(OAuth1Application.consumer_key == consumer_key)
            return await session.scalar(stmt)
